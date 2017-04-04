from django.test import TestCase
from django.urls import reverse

from main.models import User, Option, OAuth2Storage, File, Directory


class APITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='foo@bar.org')
        cls.option = Option.objects.create(user=cls.user)
        cls.dropbox = OAuth2Storage.objects.create(
            provider=OAuth2Storage.PROVIDER_DROPBOX)
        cls.dir = Directory.objects.create(path='/foo', user=cls.user)
        cls.file = File.objects.create(path='/foo/bar.txt', user=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def test_cloud_list(self):
        r = self.client.get(reverse('api:public_clouds'), {'format': 'json'})
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, len(r.json()))

    def test_me(self):
        r = self.client.get(reverse('api:me'), {'format': 'json'})
        self.assertEqual(200, r.status_code)
        self.assertIn('uid', r.json())
        self.assertIn('email', r.json())
        self.assertIn('full_name', r.json())
        self.assertIn('first_name', r.json())
        self.assertIn('last_name', r.json())

    def test_options(self):
        r = self.client.get(reverse('api:options'), {'format': 'json'})
        self.assertEqual(200, r.status_code)

    def test_dirs_path(self):
        r = self.client.get(reverse('api:dirs_path', args=('/',)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)

    def test_files_path(self):
        r = self.client.get(reverse('api:files_path', args=('/foo/bar.txt',)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)
