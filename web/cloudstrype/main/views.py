import string
import random
import logging

from django.contrib.auth import login, logout
from django.db import transaction, IntegrityError
from django.shortcuts import (
    redirect, get_object_or_404
)
from django.http import HttpResponseBadRequest, Http404
from django.views import View
from django.views.generic import RedirectView
from django.urls import reverse

from main.models import (
    OAuth2Provider, User, OAuth2AccessToken, OAuth2LoginToken
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

        state = request.GET.get('state', None)
        if state:
            state = '%s:%s' % (
                ''.join(random.sample(string.printable, 10)), state)

        return provider.get_client(redirect_uri, state=state)

    def step_one(self, request, provider_name):
        """
        Start the OAuth workflow.
        """
        client = self.get_oauth2_client(request, provider_name)

        url, state = client.authorization_url()
        request.session['oauth2_state_%s' % provider_name] = state

        return redirect(url)

    def step_two(self, request, provider_name):
        """
        Complete the OAuth workflow.
        """
        client = self.get_oauth2_client(request, provider_name)

        try:
            # Retrieve the state saved in step 1.
            client.oauthsession._state = \
                request.session.pop('oauth2_state_%s' % provider_name)
        except KeyError:
            raise Http400()

        return client.fetch_token(request.build_absolute_uri())

    def step_three(self, request):
        raise NotImplementedError('There is no step three!')


class Login(OAuth2View):
    """
    Begins OAuth2 workflow.
    """

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

    @transaction.atomic
    def get(self, request, provider_name):
        client = self.get_oauth2_client(request, provider_name)

        try:
            access_token, refresh_token, expires = self.step_two(request,
                                                                 provider_name)
        except Http400:
            return HttpResponseBadRequest('Missing state')

        client.oauthsession.token = {'access_token': access_token}
        uid, email = client.get_profile()

        action = 'expand' if 'expand' in client.oauthsession._state else None

        if action == 'expand':
            user = request.user
        else:
            try:
                # Try to fetch the user and log them in.
                user = User.objects.get(uid=uid)
                action = 'login'
            except User.DoesNotExist:
                try:
                    user = User.objects.create_user(uid=uid, email=email)
                except IntegrityError:
                    return HttpResponseBadRequest('User already registered')
                action = 'signup'

        # We want to save the token if the user is signing up, or if they are
        # expanding their storage.
        if action in ('signup', 'expand'):
            token = OAuth2AccessToken.objects.create(
                provider=client.provider, user=user,
                access_token=access_token, refresh_token=refresh_token,
                expires=expires)

        # We want to mark the token as the login token only if the user is
        # signing up.
        if action == 'signup':
            OAuth2LoginToken.objects.create(user=user, token=token)

        login(request, user)
        return redirect('/static/html/main.html')


class Logout(RedirectView):
    """
    Log the user out then redirect them.
    """

    url = '/'

    def get(self, request):
        "Log user out, let base class redirect."
        logout(request)
        return super().get(request)
