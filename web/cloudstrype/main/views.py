import logging

from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction, IntegrityError
from django.shortcuts import (
    redirect, get_object_or_404
)
from django.http import HttpResponseBadRequest, Http404
from django.views import View
from django.views.generic import RedirectView
from django.urls import reverse

from main.models import (
    OAuth2Provider, User, OAuth2AccessToken, OAuth2StorageToken,
)


LOGGER = logging.getLogger(__name__)


class Http400(Http404):
    pass


class OAuth2View(View):
    """
    OAuth2 workflow.
    """

    def get_oauth2_client(self, request, provider_name):
        for id, name in OAuth2Provider.PROVIDERS.items():
            # split() so that 'Google Drive' becomes 'google'
            if name.lower().split(' ')[0] == provider_name:
                break
        else:
            raise Http404()

        redirect_uri = reverse('main:login_complete', args=[provider_name])
        redirect_uri = request.build_absolute_uri(redirect_uri)

        provider = get_object_or_404(OAuth2Provider, provider=id)

        return provider.get_client(redirect_uri)

    def step_one(self, request, provider_name):
        """
        Start the OAuth workflow.
        """
        client = self.get_oauth2_client(request, provider_name)

        url, state = client.authorization_url()
        # Store the generated state for validation in step two.
        request.session['oauth2_state_%s' % provider_name] = state

        return redirect(url)

    def step_two(self, request, provider_name):
        """
        Complete the OAuth workflow.
        """
        client = self.get_oauth2_client(request, provider_name)

        try:
            # Retrieve the state saved in step 1.
            client.oauthsession._state = state = \
                request.session.pop('oauth2_state_%s' % provider_name)
        except KeyError:
            raise Http400()

        return client.fetch_token(request.build_absolute_uri()), state

    def step_three(self, request):
        raise NotImplementedError('There is no step three!')


class Login(OAuth2View):
    """
    Begins OAuth2 workflow.
    """

    def get(self, request, provider_name):
        request.session['oauth2_action_%s' % provider_name] = 'expand'
        return self.step_one(request, provider_name)


class LoginComplete(OAuth2View):
    """
    Completes OAuth2 workflow.

    Handles new users by creating an account for them before logging them in.

    Depends on the provider giving a UID for the user, and also providing their
    email address. However, if email is not present, we prompt the user for
    one.
    """

    @transaction.atomic
    def get(self, request, provider_name):
        client = self.get_oauth2_client(request, provider_name)

        try:
            (access_token, refresh_token, expires), state = self.step_two(
                request, provider_name)
        except Http400:
            return HttpResponseBadRequest('Missing state')

        client.oauthsession.token = {'access_token': access_token}
        uid, email, name, size, used = client.get_profile()

        if request.user.is_authenticated():
            user = request.user
        else:
            try:
                # Try to fetch the user and log them in.
                user = User.objects.get(tokens__provider_uid=uid)
            except User.DoesNotExist:
                try:
                    user = User.objects.create_user(email=email,
                                                    full_name=name)
                except IntegrityError:
                    return HttpResponseBadRequest('User already registered '
                                                  '-- login and try again.')

        # If the token exists, update it. Otherwise create it.
        try:
            token, _ = OAuth2AccessToken.objects.get_or_create(
                provider=client.provider, user=user, provider_uid=uid)
        except IntegrityError:
            return HttpResponseBadRequest('Cloud already registered to user')
        token.access_token = access_token
        token.refresh_token = refresh_token
        token.expires = expires
        token.save()

        if client.provider.is_storage:
            OAuth2StorageToken.objects.create(user=user, token=token,
                                              size=size, used=used)

        login(request, user)

        return redirect(reverse('ui:home'))


class Logout(RedirectView):
    """
    Log the user out then redirect them.
    """

    @property
    def url(self):
        "Replace property. Can't reverse during import."
        return reverse('ui:start')

    def get(self, request):
        "Log user out, let base class redirect."
        logout(request)
        return super().get(request)


class EmailConfirm(RedirectView):
    """
    Handle email confirmation link.
    """

    @property
    def url(self):
        "Replace property. Can't reverse during import."
        return reverse('ui:start')

    def get(self, request, uid, token):
        user = get_user_model().objects.get(uid=uid)
        if default_token_generator.check_token(user, token):
            user.is_active = True
            user.save()
            return super().get(request)
        raise Http404()
