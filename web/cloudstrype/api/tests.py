import mock

from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient

from main.models import (
    User, Option, Storage, UserFile, UserDir, Tag,
)
from main.tests.test_fs import MockClients


TEST_FILE_BODY = b'Test file body.'


class APIFSTestCase(TestCase):
    """
    API tests that require FS.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(email='foo@bar.org')

    def setUp(self):
        self.client = APIClient()
        self.client.force_login(self.user)

    def test_upload_download(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            # TODO: I would like to test multipart upload as well.
            r = self.client.post(
                reverse('api:files_data_path', args=('/foo',)), TEST_FILE_BODY,
                content_type="application/octet-stream")
            self.assertEqual(200, r.status_code)
            # TODO: I cannot figure out how to post multipart and receive JSON
            # self.assertEqual(15, len(r.json()))

            # A file object should now exist, we can access it by path.
            r = self.client.get(reverse('api:files_data_path', args=('/foo',)),
                                {'format': 'json'})
            self.assertEqual(200, r.status_code)
            self.assertEqual(TEST_FILE_BODY,
                             b''.join(list(r.streaming_content)))

            # A file object should now exist, we can access it by uid.
            file = UserFile.objects.first()
            r = self.client.get(reverse('api:files_data_uid',
                                        args=(file.uid,)),
                                {'format': 'json'})
            self.assertEqual(200, r.status_code)
            self.assertEqual(TEST_FILE_BODY,
                             b''.join(list(r.streaming_content)))

            # Ensure we can download a specific version of a file.
            r = self.client.get(reverse('api:files_version_data_path',
                                        args=(file.path,
                                              file.file.version.uid)),
                                {'format': 'json'})
            self.assertEqual(200, r.status_code)
            self.assertEqual(TEST_FILE_BODY,
                             b''.join(list(r.streaming_content)))

            # Ensure we can download a specific version of a file by uid.
            r = self.client.get(reverse('api:files_version_data_uid',
                                        args=(file.uid,
                                              file.file.version.uid)),
                                {'format': 'json'})
            self.assertEqual(200, r.status_code)
            self.assertEqual(TEST_FILE_BODY,
                             b''.join(list(r.streaming_content)))


class APITestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='foo@bar.org')
        cls.option = Option.objects.create(user=cls.user)
        cls.storage = Storage.objects.create(
            type=Storage.TYPE_DROPBOX, user=cls.user)
        cls.dir = UserDir.objects.create(path='/foo', user=cls.user)
        cls.file = UserFile.objects.create(path='/foo/bar.txt', user=cls.user)
        cls.tags = [
            Tag.objects.create(name='foo'),
            Tag.objects.create(name='bar'),
            Tag.objects.create(name='baz'),
        ]
        cls.file.add_tag('foo')
        cls.file.add_tag('bar')
        cls.dir.add_tag('baz')

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
