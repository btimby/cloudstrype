import time
import json

from urllib.parse import parse_qs, urlparse

import httpretty

from django.test import TestCase, Client
from django.urls import reverse

from main.models import BaseStorage, OAuth2Storage

from main.fs.clouds import get_client


ACCESS_TOKEN = {
    'access_token': '1234',
    'refresh_token': '5678',
    'expires': time.time()+600,
}
USER_PROFILE = {
    'dropbox': {
        'account_id': '1234',
        'email': 'foo@bar.org',
        'name': {
            'display_name': 'Foo Bar',
        },
        'allocation': {
            'allocated': 1000,
        },
        'used': 100,
    },
    'onedrive': {
        'id': '1234',
        'emails': {
            'account': 'foo@bar.org',
        },
        'name': 'Foo Bar',
        'quota': {
            'total': 1000,
            'used': 100,
        },
    },
    'box': {
        'id': '1234',
        'login': 'foo@bar.org',
        'name': 'Foo Bar',
        'space_amount': 1000,
        'space_used': 100,
    },
    'google': {
        'id': '1234',
        'email': 'foo@bar.org',
        'name': 'Foo Bar',
        'quotaBytesTotal': 1000,
        'quotaBytesUsed': 100,
    },
}
METHODS = {
    'get': httpretty.GET,
    'post': httpretty.POST,
}


class NonProviderLoginTestCase(TestCase):
    """
    An invalid provider name should 404.
    """

    def test_login_provider(self):
        r = self.client.get(reverse('login_oauth2', args=('wtf', )))
        self.assertEqual(404, r.status_code)


class BaseLogin(object):
    """
    Test each OAuth2 provider.
    """

    def setUp(self):
        self.client = Client()
        self.provider = OAuth2Storage.objects.create(provider=self.PROVIDER)
        httpretty.enable()
        oauth2 = get_client(self.provider)
        httpretty.register_uri(httpretty.POST, oauth2.ACCESS_TOKEN_URL,
                               body=json.dumps(ACCESS_TOKEN),
                               content_type='application/json')
        httpretty.register_uri(
            METHODS.get(oauth2.USER_PROFILE_URL[0]),
            oauth2.USER_PROFILE_URL[1],
            body=json.dumps(USER_PROFILE[self.provider.slug]),
            content_type='application/json')
        if oauth2.USER_STORAGE_URL:
            httpretty.register_uri(
                METHODS.get(oauth2.USER_STORAGE_URL[0]),
                oauth2.USER_STORAGE_URL[1],
                body=json.dumps(USER_PROFILE[self.provider.slug]),
                content_type='application/json')

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()

    def test_step_one(self):
        r = self.client.get(reverse('login_oauth2',
                            args=(self.provider.slug, )))
        self.assertEqual(302, r.status_code)

    def test_step_two(self):
        r = self.client.get(reverse('login_oauth2',
                            args=(self.provider.slug, )))
        qs = r.url.split('?', 1)[1]
        qs = parse_qs(qs)
        urlp = urlparse(qs['redirect_uri'][0])

        # This view makes several calls to the OAuth provider. setUp() has
        # mocked these HTTP calls, so the view can operate.
        r = self.client.get(urlp.path, {
            'state': qs['state'][0], 'code': '1234'
        })

        # Make assertions about the user created above.


class DropboxLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_DROPBOX


class OnedriveLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_ONEDRIVE


class BoxLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_BOX


class GoogleLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_GOOGLE
