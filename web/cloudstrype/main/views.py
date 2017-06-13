import logging

from django.contrib.auth import login as _login
from django.contrib.auth import logout as _logout
from django.db import transaction, IntegrityError
from django.shortcuts import redirect, render
from django.http import HttpResponseBadRequest, Http404
from django.views import View
from django.urls import reverse

from main.models import (
    Storage, User
)
from main.fs.clouds import get_client


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
                    user.storages.order_by('id').first().slug
        if provider:
            return redirect(reverse('login_oauth2', args=(provider,)))
    return render(request, 'main/login.html')


def logout(request):
    "Simple logout view."
    _logout(request)
    return redirect(reverse('ui:home'))


class OAuth2View(View):
    """
    OAuth2 workflow.
    """

    def _get_oauth2_client(self, request, provider_name):
        for type, slug in Storage.TYPE_SLUGS.items():
            if slug == provider_name:
                break
        else:
            raise Http404()

        redirect_uri = reverse('complete_oauth2', args=[provider_name])
        redirect_uri = request.build_absolute_uri(redirect_uri)

        return get_client(type, redirect_uri=redirect_uri)


class Login(OAuth2View):
    """
    Begins OAuth2 workflow.
    """

    def get(self, request, provider_name):
        next = request.GET.get('next', None)
        provider_name = provider_name.lower()
        client = self._get_oauth2_client(request, provider_name)

        url, state = client.authorization_url()
        # Store the generated state for validation in step two.
        request.session['oauth2_state_%s' % provider_name] = state, next

        return redirect(url)


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

        client = self._get_oauth2_client(request, provider_name)

        try:
            # Retrieve the state saved in step 1.
            client.oauthsession._state, next = \
                request.session.pop('oauth2_state_%s' % provider_name)
        except KeyError:
            return HttpResponseBadRequest('Missing state')

        client.oauthsession.token = token = client.fetch_token(
            request.build_absolute_uri())
        uid, email, name, size, used = client.get_profile()

        if request.user.is_authenticated():
            user = request.user
        else:
            try:
                # Try to fetch the user and log them in.
                user = User.objects.get(storages__attrs__uid=uid)
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
            try:
                storage = Storage.objects.get(user=user, type=client.TYPE,
                                              attrs__uid=uid)
            except Storage.DoesNotExist:
                storage = Storage(user=user, type=client.TYPE)
                storage.attrs = {'uid': uid}
                client.initialize(storage)
            storage.auth = token
            storage.size = size
            storage.used = used
            storage.save()
        except IntegrityError:
            return HttpResponseBadRequest('Cloud already registered to user')

        _login(request, user)

        if not next:
            next = reverse('ui:new')

        return redirect(next)
