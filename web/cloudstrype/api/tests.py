from django.test import TestCase
from django.urls import reverse

from main.models import (
    User, Option, OAuth2Storage, OAuth2UserStorage, File, Directory, Tag
)


class APITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='foo@bar.org')
        cls.option = Option.objects.create(user=cls.user)
        cls.dropbox = OAuth2Storage.objects.create(
            provider=OAuth2Storage.PROVIDER_DROPBOX)
        cls.user_dropbox = OAuth2UserStorage.objects.create(
            storage=cls.dropbox, user=cls.user)
        cls.dir = Directory.objects.create(path='/foo', user=cls.user)
        cls.file = File.objects.create(path='/foo/bar.txt', user=cls.user)
        cls.tags = [
            Tag.objects.create(name='foo'),
            Tag.objects.create(name='bar'),
            Tag.objects.create(name='baz'),
        ]
        cls.file.tags.add(cls.tags[0])
        cls.file.tags.add(cls.tags[1])
        cls.dir.tags.add(cls.tags[2])

    def setUp(self):
        self.client.force_login(self.user)

    def test_public_cloud_list(self):
        r = self.client.get(reverse('api:public_clouds'), {'format': 'json'})
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, len(r.json()))

    def test_cloud_list(self):
        r = self.client.get(reverse('api:clouds'), {'format': 'json'})
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
        r = self.client.get(reverse('api:dirs_path', args=('/bar',)),
                            {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.get(reverse('api:dirs_path', args=('/foo',)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)
        r = self.client.delete(reverse('api:dirs_path', args=('/bar',)),
                               {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.delete(reverse('api:dirs_path', args=('/foo',)),
                               {'format': 'json'})
        self.assertEqual(200, r.status_code)

    def test_dirs_uid(self):
        r = self.client.get(reverse('api:dirs_uid', args=(self.file.uid,)),
                            {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.get(reverse('api:dirs_uid', args=(self.dir.uid,)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)
        r = self.client.delete(reverse('api:dirs_uid', args=(self.file.uid,)),
                               {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.delete(reverse('api:dirs_uid', args=(self.dir.uid,)),
                               {'format': 'json'})
        self.assertEqual(200, r.status_code)

    def test_files_path(self):
        r = self.client.get(reverse('api:files_path', args=('/bar/foo.txt',)),
                            {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.get(reverse('api:files_path', args=('/foo/bar.txt',)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)
        r = self.client.delete(reverse('api:files_path',
                               args=('/bar/foo.txt',)), {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.delete(reverse('api:files_path',
                               args=('/foo/bar.txt',)), {'format': 'json'})
        self.assertEqual(200, r.status_code)

    def test_files_uid(self):
        r = self.client.get(reverse('api:files_uid', args=(self.dir.uid,)),
                            {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.get(reverse('api:files_uid', args=(self.file.uid,)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)
        r = self.client.delete(reverse('api:files_uid', args=(self.dir.uid,)),
                               {'format': 'json'})
        self.assertEqual(404, r.status_code)
        r = self.client.delete(reverse('api:files_uid', args=(self.file.uid,)),
                               {'format': 'json'})
        self.assertEqual(200, r.status_code)

    def test_tags(self):
        r = self.client.get(reverse('api:taglist'), {'format': 'json'})
        self.assertEqual(200, r.status_code)
        self.assertEqual(3, len(r.json()))

        r = self.client.get(reverse('api:tagitem', args=('foo',)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)

        r = self.client.get(reverse('api:tagitem', args=('goo',)),
                            {'format': 'json'})
        self.assertEqual(404, r.status_code)

    def test_taglist(self):
        r = self.client.get(reverse('api:dirtaglist', args=('baz',)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, len(r.json()))

        r = self.client.get(reverse('api:filetaglist', args=('foo',)),
                            {'format': 'json'})
        self.assertEqual(200, r.status_code)
        self.assertEqual(1, len(r.json()))
