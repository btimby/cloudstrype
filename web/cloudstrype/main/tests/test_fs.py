import mock

from io import BytesIO

from django.test import TestCase

from main.fs import MulticloudFilesystem
from main.fs.errors import (
    FileNotFoundError, DirectoryConflictError, FileConflictError
)
from main.models import (
    User, OAuth2Provider, OAuth2AccessToken, OAuth2StorageToken
)


TEST_FILE = b'Test file body.'


class MockClient(object):
    def __init__(self, oauth_access):
        self.oauth_access = oauth_access
        self.data = {}

    def upload(self, chunk, data):
        self.data[chunk.uid] = data

    def download(self, chunk):
        return self.data[chunk.uid]

    def delete(self, chunk):
        del self.data[chunk.uid]


class MockClients(object):
    def __init__(self, user):
        self.user = user

    def get_clients(self):
        provider = OAuth2Provider.objects.create(
            provider=OAuth2Provider.PROVIDER_DROPBOX)

        clients = []
        for i in range(4):
            access_token = OAuth2AccessToken.objects.create(
                provider=provider, user=self.user)
            storage_token = OAuth2StorageToken.objects.create(
                user=self.user, token=access_token)
            clients.append(MockClient(storage_token))
        return clients


class FilesystemTestCase(TestCase):
    def test_fs(self):
        user = User.objects.create(email='foo@bar.org')
        with mock.patch('main.models.User.get_clients',
                        MockClients(user).get_clients):
            fs = MulticloudFilesystem(user)

            with BytesIO(TEST_FILE) as f:
                file = fs.upload('/foo', f)

            self.assertEqual('/foo', file.path)

            with fs.download('/foo') as f:
                self.assertEqual(TEST_FILE, f.read())

            with self.assertRaises(FileNotFoundError):
                fs.download('/barfoo')

            fs.delete('/foo')

    def test_mkdir(self):
        user = User.objects.create(email='foo@bar.org')
        fs = MulticloudFilesystem(user)
        dir = fs.mkdir('/foo')
        self.assertEqual('/foo', dir.path)

    def test_move(self):
        user = User.objects.create(email='foo@bar.org')
        fs = MulticloudFilesystem(user)
        fs.mkdir('/foo')
        fs.mkdir('/bar')
        fs.move('/foo', '/bar')

        self.assertFalse(fs.exists('/foo'))
        self.assertTrue(fs.exists('/bar/foo'))
        self.assertTrue(fs.isdir('/bar/foo'))

    def test_move_file(self):
        user = User.objects.create(email='foo@bar.org')
        with mock.patch('main.models.User.get_clients',
                        MockClients(user).get_clients):
            fs = MulticloudFilesystem(user)

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            # Dst directories are created automatically.
            fs.move('/foo', '/bar')

            self.assertTrue(fs.exists('/bar/foo'))
            self.assertTrue(fs.isdir('/bar'))
            self.assertTrue(fs.isfile('/bar/foo'))
            self.assertFalse(fs.exists('/foo'))

    def test_move_fail(self):
        user = User.objects.create(email='foo@bar.org')
        with mock.patch('main.models.User.get_clients',
                        MockClients(user).get_clients):
            fs = MulticloudFilesystem(user)

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            with self.assertRaises(FileConflictError):
                fs.mkdir('/foo')

            fs.mkdir('/bar/foo')

            with self.assertRaises(DirectoryConflictError):
                fs.move('/foo', '/bar')

    def test_copy(self):
        user = User.objects.create(email='foo@bar.org')
        fs = MulticloudFilesystem(user)
        fs.mkdir('/foo')
        fs.mkdir('/bar')
        fs.copy('/foo', '/bar')

        self.assertTrue(fs.exists('/foo'))
        self.assertTrue(fs.exists('/bar/foo'))
        self.assertTrue(fs.isdir('/foo'))
        self.assertTrue(fs.isdir('/bar/foo'))

    def test_copy_file(self):
        user = User.objects.create(email='foo@bar.org')
        with mock.patch('main.models.User.get_clients',
                        MockClients(user).get_clients):
            fs = MulticloudFilesystem(user)

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            # Dst directories are created automatically.
            fs.copy('/foo', '/bar')

            self.assertTrue(fs.exists('/bar/foo'))
            self.assertTrue(fs.isdir('/bar'))
            self.assertTrue(fs.isfile('/bar/foo'))
            self.assertTrue(fs.exists('/foo'))

    def test_copy_fail(self):
        user = User.objects.create(email='foo@bar.org')
        with mock.patch('main.models.User.get_clients',
                        MockClients(user).get_clients):
            fs = MulticloudFilesystem(user)

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            with self.assertRaises(FileConflictError):
                fs.mkdir('/foo')

            fs.mkdir('/bar/foo')

            with self.assertRaises(DirectoryConflictError):
                fs.copy('/foo', '/bar')
