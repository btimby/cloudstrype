import time
import json

from urllib.parse import parse_qs, urlparse

import httpretty

from django.test import TestCase, Client
from django.urls import reverse

from main.models import User, BaseStorage, OAuth2Storage, OAuth2UserStorage

from main.fs.clouds import get_client


ACCESS_TOKEN = {
    'access_token': '1234',
    'refresh_token': '5678',
    'expires': time.time()+600,
}

USER_PROFILE_DROPBOX = {
    'account_id': '1234',
    'email': 'foo@bar.org',
    'name': {
        'display_name': 'Foo Bar',
    },
    'allocation': {
        'allocated': 1000,
    },
    'used': 100,
}
USER_PROFILE_ONEDRIVE = {
    'id': '1234',
    'emails': {
        'account': 'foo@bar.org',
    },
    'name': 'Foo Bar',
    'quota': {
        'total': 1000,
        'used': 100,
    },
}
USER_PROFILE_BOX = {
    'id': '1234',
    'login': 'foo@bar.org',
    'name': 'Foo Bar',
    'space_amount': 1000,
    'space_used': 100,
}
USER_PROFILE_GOOGLE = {
    'id': '1234',
    'email': 'foo@bar.org',
    'name': 'Foo Bar',
    'quotaBytesTotal': 1000,
    'quotaBytesUsed': 100,
}
CREATE_BOX = {
    'id': 'abc123',
}
CREATE_GOOGLE = {
    'items': [
        {'id': 'abc123'}
    ]
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


class LoginTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.storage = OAuth2Storage.objects.create(
            provider=BaseStorage.PROVIDER_DROPBOX)
        cls.user = User.objects.create(email='foo@bar.org')
        cls.oauth2 = OAuth2UserStorage.objects.create(
                storage=cls.storage, user=cls.user)

    def test_login_get(self):
        r = self.client.get(reverse('login'))
        self.assertEqual(200, r.status_code)

    def test_login_post_provider(self):
        r = self.client.post(reverse('login'),
                             {'provider': self.storage.name})
        self.assertEqual(302, r.status_code)

    def test_login_post_email(self):
        r = self.client.post(reverse('login'), {'email': 'foo@bar.org'})
        self.assertEqual(302, r.status_code)


class LogoutTestCase(TestCase):
    def test_logout_get(self):
        r = self.client.get(reverse('logout'))
        self.assertEqual(302, r.status_code)


class BaseLogin(object):
    """
    Test each OAuth2 provider.
    """

    @classmethod
    def setUpTestData(cls):
        cls.provider = OAuth2Storage.objects.create(provider=cls.PROVIDER)
        cls.oauth2_client = get_client(cls.provider)

    def setUp(self):
        httpretty.enable()
        httpretty.register_uri(
            httpretty.POST, self.oauth2_client.ACCESS_TOKEN_URL,
            body=json.dumps(ACCESS_TOKEN),
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

    def setUp(self):
        super().setUp()
        httpretty.register_uri(
            METHODS.get(self.oauth2_client.USER_PROFILE_URL[0]),
            self.oauth2_client.USER_PROFILE_URL[1],
            body=json.dumps(USER_PROFILE_DROPBOX),
            content_type='application/json')
        httpretty.register_uri(
            METHODS.get(self.oauth2_client.USER_STORAGE_URL[0]),
            self.oauth2_client.USER_STORAGE_URL[1],
            body=json.dumps(USER_PROFILE_DROPBOX),
            content_type='application/json')


class OnedriveLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_ONEDRIVE

    def setUp(self):
        super().setUp()
        httpretty.register_uri(
            METHODS.get(self.oauth2_client.USER_PROFILE_URL[0]),
            self.oauth2_client.USER_PROFILE_URL[1],
            body=json.dumps(USER_PROFILE_ONEDRIVE),
            content_type='application/json')
        httpretty.register_uri(
            METHODS.get(self.oauth2_client.USER_STORAGE_URL[0]),
            self.oauth2_client.USER_STORAGE_URL[1],
            body=json.dumps(USER_PROFILE_ONEDRIVE),
            content_type='application/json')


class BoxLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_BOX

    def setUp(self):
        super().setUp()
        httpretty.register_uri(
            METHODS.get(self.oauth2_client.USER_PROFILE_URL[0]),
            self.oauth2_client.USER_PROFILE_URL[1],
            body=json.dumps(USER_PROFILE_BOX),
            content_type='application/json')
        httpretty.register_uri(httpretty.POST, self.oauth2_client.CREATE_URL,
                               body=json.dumps(CREATE_BOX),
                               content_type='application/json')


class GoogleLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_GOOGLE

    def setUp(self):
        super().setUp()
        httpretty.register_uri(
            METHODS.get(self.oauth2_client.USER_PROFILE_URL[0]),
            self.oauth2_client.USER_PROFILE_URL[1],
            body=json.dumps(USER_PROFILE_GOOGLE),
            content_type='application/json')
        httpretty.register_uri(
            METHODS.get(self.oauth2_client.USER_STORAGE_URL[0]),
            self.oauth2_client.USER_STORAGE_URL[1],
            body=json.dumps(USER_PROFILE_GOOGLE),
            content_type='application/json')
        httpretty.register_uri(httpretty.GET, self.oauth2_client.CREATE_URL,
                               body=json.dumps(CREATE_GOOGLE),
                               content_type='application/json')
