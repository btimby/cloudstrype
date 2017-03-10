import mock
import shutil

from io import BytesIO

from django.test import TestCase

from main.fs import MulticloudFilesystem
from main.fs.errors import (
    PathNotFoundError, FileNotFoundError, DirectoryNotFoundError,
    DirectoryConflictError, FileConflictError
)
from main.models import (
    User, OAuth2Provider, OAuth2AccessToken, OAuth2StorageToken
)


TEST_FILE = b'Test file body.'


class MockClient(object):
    def __init__(self, oauth_storage):
        self.oauth_storage = oauth_storage
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

        provider = OAuth2Provider.objects.create(
            provider=OAuth2Provider.PROVIDER_DROPBOX)

        self.clients = []
        for i in range(4):
            access_token = OAuth2AccessToken.objects.create(
                provider=provider, user=self.user)
            storage_token = OAuth2StorageToken.objects.create(
                user=self.user, token=access_token)
            self.clients.append(MockClient(storage_token))

    def get_clients(self):
        return self.clients


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

            with self.assertRaises(FileNotFoundError):
                fs.delete('/foo')

    def test_fs_replicas(self):
        user = User.objects.create(email='foo@bar.org')
        mock_clients = MockClients(user)
        with mock.patch('main.models.User.get_clients',
                        mock_clients.get_clients):
            fs = MulticloudFilesystem(user, chunk_size=3, replicas=2)

            with BytesIO(TEST_FILE) as f:
                file = fs.upload('/foo', f)

            mock_clients.clients[2].data.clear()

            self.assertEqual('/foo', file.path)

            with BytesIO() as o:
                with fs.download('/foo') as f:
                    shutil.copyfileobj(f, o)
                    self.assertEqual(TEST_FILE, o.getvalue())

            with self.assertRaises(FileNotFoundError):
                fs.download('/barfoo')

            fs.delete('/foo')

    def test_mkdir(self):
        user = User.objects.create(email='foo@bar.org')
        fs = MulticloudFilesystem(user)
        dir = fs.mkdir('/foo')
        self.assertEqual('/foo', dir.path)
        fs.rmdir('/foo')
        with self.assertRaises(DirectoryNotFoundError):
            fs.rmdir('/foo')

    def test_listdir(self):
        user = User.objects.create(email='foo@bar.org')
        fs = MulticloudFilesystem(user)
        fs.mkdir('/foo')
        fs.mkdir('/foo/bar')
        fs.mkdir('/foo/baz')

        listing = fs.listdir('/foo')
        self.assertEqual(2, len(listing.dirs))
        self.assertEqual(0, len(listing.files))

        with self.assertRaises(DirectoryNotFoundError):
            fs.listdir('/missing')

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

            self.assertTrue(fs.exists('/bar'))
            self.assertTrue(fs.isfile('/bar'))
            self.assertFalse(fs.exists('/foo'))

    def test_move_fail(self):
        user = User.objects.create(email='foo@bar.org')
        with mock.patch('main.models.User.get_clients',
                        MockClients(user).get_clients):
            fs = MulticloudFilesystem(user)

            with self.assertRaises(PathNotFoundError):
                fs.move('/foo', '/bar')

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            with self.assertRaises(FileConflictError):
                fs.mkdir('/foo')

            fs.mkdir('/bar/foo')

            with self.assertRaises(DirectoryConflictError):
                fs.move('/foo', '/bar')

            with self.assertRaises(DirectoryConflictError):
                fs.move('/bar', '/foo')

            with self.assertRaises(DirectoryNotFoundError):
                fs.move('/bar/foo', '/missing/bar')

            with self.assertRaises(DirectoryNotFoundError):
                fs.move('/foo', '/missing/bar')

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
            fs.copy('/foo', '/miss')
            fs.copy('/foo', '/bar')

            self.assertTrue(fs.isfile('/bar'))
            self.assertTrue(fs.isfile('/foo'))

            with BytesIO() as o:
                with fs.download('/bar') as f:
                    shutil.copyfileobj(f, o)
                    self.assertEqual(TEST_FILE, o.getvalue())

            with self.assertRaises(FileConflictError):
                fs.copy('/foo', '/bar')

            with BytesIO(TEST_FILE) as f:
                fs.upload('/bar/baz', f)
            with BytesIO(TEST_FILE) as f:
                fs.upload('/baz', f)

            with self.assertRaises(FileConflictError):
                fs.copy('/baz', '/bar')

            with self.assertRaises(PathNotFoundError):
                fs.copy('/missing', 'bar')

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

    def test_info(self):
        user = User.objects.create(email='foo@bar.org')
        with mock.patch('main.models.User.get_clients',
                        MockClients(user).get_clients):
            fs = MulticloudFilesystem(user)

            with self.assertRaises(FileNotFoundError):
                fs.info('/foo')

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            fs.info('/foo')
