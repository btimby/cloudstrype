from django.test import TestCase, Client
from django.urls import reverse

from main.models import BaseStorage, OAuth2Storage


class BaseLogin(object):
    def setUp(self):
        self.client = Client()
        self.provider = OAuth2Storage.objects.create(provider=self.PROVIDER)

    def test_login_provider(self):
        r = self.client.get(reverse('login_oauth2',
                            args=(self.provider.slug, )))
        self.assertEqual(302, r.status_code)


class DropboxLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_DROPBOX


class OnedriveLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_ONEDRIVE


class BoxLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_BOX


class GoogleLoginTestCase(BaseLogin, TestCase):
    PROVIDER = BaseStorage.PROVIDER_GOOGLE
