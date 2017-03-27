import logging

from django.contrib.auth import login as _login
from django.contrib.auth import logout as _logout
from django.db import transaction, IntegrityError
from django.shortcuts import (
    redirect, get_object_or_404, render
)
from django.http import HttpResponseBadRequest, Http404
from django.views import View
from django.urls import reverse

from main.models import (
    BaseStorage, User, OAuth2Storage,
)


LOGGER = logging.getLogger(__name__)


def login(request):
    """
    Let user choose provider.

    Otherwise handles POST from quick login form on index.html template or
    full provider-selection form on login.html.
    """
    if request.method == 'POST':
        provider = request.POST.get('provider', None)
        email = request.POST.get('email', None)
        if not provider and email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass
            else:
                provider = \
                    user.tokens.order_by('id').first().provider.name.lower()
        if provider:
            return redirect(reverse('login_oauth2', args=(provider,)))
    return render(request, 'main/login.html')


def logout(request):
    "Simple logout view."
    _logout(request)
    return redirect(reverse('ui:home'))


class Http400(Http404):
    "Throwable 400 error."

    pass


class OAuth2View(View):
    """
    OAuth2 workflow.
    """

    def get_oauth2_client(self, request, provider_name):
        for id, name in BaseStorage.PROVIDERS.items():
            # split() so that 'Google Drive' becomes 'google'
            if name.lower().split(' ')[0] == provider_name:
                break
        else:
            raise Http404()

        redirect_uri = reverse('complete_oauth2', args=[provider_name])
        redirect_uri = request.build_absolute_uri(redirect_uri)

        provider = get_object_or_404(BaseStorage, provider=id)

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
        provider_name = provider_name.lower()
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
        if 'error' in request.GET:
            return redirect(reverse('login'))
        provider_name = provider_name.lower()
        client = self.get_oauth2_client(request, provider_name)

        try:
            token, state = self.step_two(
                request, provider_name)
        except Http400:
            return HttpResponseBadRequest('Missing state')

        client.oauthsession.token = token
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
                else:
                    # TODO: send new user a welcome email.
                    pass

        # If the token exists, update it. Otherwise create it.
        try:
            oauth_access, _ = OAuth2Storage.objects.get_or_create(
                provider=client.provider, user=user, provider_uid=uid,
                size=size, used=used)
        except IntegrityError:
            return HttpResponseBadRequest('Cloud already registered to user')
        oauth_access.update(**token)
        oauth_access.save()

        _login(request, user)

        return redirect(reverse('ui:new'))
