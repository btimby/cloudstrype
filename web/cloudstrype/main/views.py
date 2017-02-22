import logging

from django.contrib.auth import login, logout
from django.db import transaction, IntegrityError
from django.shortcuts import (
    render, redirect, get_object_or_404
)
from django.http import HttpResponseBadRequest, Http404
from django.views import View
from django.views.generic import RedirectView
from django.urls import reverse

from requests_oauthlib import OAuth2Session

from main.models import (
    OAuth2Provider, User, OAuth2AccessToken
)


LOGGER = logging.getLogger(__name__)


class Http400(Http404):
    pass


class OAuth2View(View):
    """
    OAuth2 workflow.
    """

    def _get_oauth_session(self, request, provider_name):
        provider = get_object_or_404(OAuth2Provider, name=provider_name)

        redirect_uri = reverse(self.COMPLETE_VIEW, args=[provider_name])
        redirect_uri = request.build_absolute_uri(redirect_uri)

        return OAuth2Session(provider.client_id, redirect_uri=redirect_uri,
            scope=provider.scope), provider

    def step_one(self, request, provider_name):
        """
        Start the OAuth workflow.
        """
        oauth, provider = self._get_oauth_session(request, provider_name)

        url, state = oauth.authorization_url(provider.authorization_url)
        request.session['oauth2_state_%s' % provider_name] = state

        return redirect(url)

    def step_two(self, request, provider_name):
        """
        Complete the OAuth workflow.
        """
        oauth, provider = self._get_oauth_session(request, provider_name)

        try:
            # Retrieve the state saved in step 1.
            oauth._state = request.session.pop('oauth2_state_%s' % \
                provider_name)
        except KeyError:
            raise Http400()

        return oauth.fetch_token(
            provider.access_token_url,
            authorization_response=request.build_absolute_uri(),
            client_secret=provider.client_secret), oauth, provider

    def step_three(self, request):
        raise NotImplementedError('There is no step three!')


class Login(OAuth2View):
    """
    Begins OAuth2 workflow.
    """

    COMPLETE_VIEW = 'main:login_complete'

    def get(self, request, provider_name):
        return self.step_one(request, provider_name)


class LoginComplete(OAuth2View):
    """
    Completes OAuth2 workflow.

    Handles new users by creating an account for them before logging them in.

    Depends on the provider giving a UID for the user, and also providing their
    email address. However, if email is not present, we prompt the user for
    one.
    """

    COMPLETE_VIEW = 'main:login_complete'

    def post(self, request):
        "Save user after receiving email from form."
        form = EmailForm(request.POST)
        if not form.is_valid():
            return render('main/get_email.html', form)
        user = self.save_user(**session_data)
        login(request, user)
        return redirect('/static/html/main.html')

    def get_user_email(self, request, provider_name, token):
        request.session['oauth2_token_%s' % provider_name] = token
        form = EmailForm()
        return render('main/get_email.html', form)

    def save_user(self, uid, email, token):
        user = User.objects.create_user(uid=uid, email=email)
        # Only save the token for new users, we don't want to invalidate
        # the old token.
        # TODO: save expires
        OAuth2AccessToken.objects.create(provider=provider, user=user,
            access_token=token['access_token'])
        return user

    @transaction.atomic
    def get(self, request, provider_name):
        try:
            token, oauth, provider = self.step_two(request, provider_name)
        except Http400:
            return HttpResponseBadRequest('Missing state')

        # Get profile data, and field mappings.
        profile = oauth.get(provider.user_profile_url).json()
        uid_field, email_field = 'uid', 'email'
        if provider.fields:
            uid_field = provider.fields.get('uid', uid_field)
            email_field = provider.fields.get('email', email_field)

        # Get uid and email (needed to fetch or create the user).
        def _get_profile_field(field_name):
            if isinstance(field_name, str):
                return profile.get(field_name)
            else:
                value, field_name = profile, field_name[:]
                while field_name:
                    value = value.get(field_name.pop(0))
                return value

        uid = _get_profile_field(uid_field)
        try:
            email = _get_profile_field(email_field)
        except ValueError:
            email = None

        try:
            # Try to fetch the user and log them in.
            user = User.objects.get(uid=uid)
        except User.DoesNotExist:
            # User is a new user.
            if not email:
                return self.get_user_email(request, provider_name, profile, token)
            try:
                # Email already used by another account (different uid).
                user = self.save_user(uid, email, token)
            except IntegrityError:
                return self.get_user_email(request, provider_name, profile, token)

        login(request, user)
        return redirect('/static/html/main.html')


class Expand(Login):
    """
    Allow the user to expand storage to new provider.

    Reuses the OAuth workflow from Login view.
    """

    COMPLETE_VIEW = 'main:expand_complete'

    def get(self, request, provider_name):
        provider = get_object_or_404(OAuth2Provider, name=provider_name)
        # Ensure this is a unique provider:
        try:
            OAuth2AccessToken.objects.get(user=request.user, provider=provider)
            return HttpResponseBadRequest('Provider already registered')
        except OAuth2AccessToken.DoesNotExist:
            pass

        return self.step_one(request, provider_name)


class ExpandComplete(LoginComplete):
    """
    Add new provider to user account.

    Reuses the OAuth workflow from LoginComplete view.
    """

    COMPLETE_VIEW = 'main:login_complete'

    def get(self, request, provider_name):
        # The user is logged in, so add the new token.
        try:
            token, oauth, provider = self.get_token(request, provider_name)
        except Http400:
            return HttpResponseBadRequest('Missing state')

        # TODO: save expires
        try:
            OAuth2AccessToken.objects.create(provider=provider, user=user,
                access_token=token['access_token'])
        except IntegrityError:
            return HttpResponseBadRequest('Provider already registered')

        return redirect('/static/html/main.html')


class Logout(RedirectView):
    """
    Log the user out then redirect them.
    """

    url = '/'

    def get(self, request):
        logout(request)
        return super().get(request)
