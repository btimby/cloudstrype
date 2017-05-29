import mock
import shutil

from io import BytesIO

from django.test import TestCase

from main.fs import get_fs
from main.fs.clouds import get_client
from main.fs.errors import (
    PathNotFoundError, FileNotFoundError, DirectoryNotFoundError,
    DirectoryConflictError, FileConflictError,
)
from main.models import (
    User, Storage,
)


TEST_FILE = b'Test file body.'


class MockClient(object):
    def __init__(self, storage):
        self.storage = storage
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
        self.clients = []

        for i in range(4):
            storage = Storage.objects.create(type=Storage.TYPE_DROPBOX,
                                             user=self.user)
            self.clients.append(MockClient(storage))

    def get_clients(self):
        return self.clients


class FilesystemTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(email='foo@bar.org')

    def test_fs(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)

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
        mock_clients = MockClients(self.user)
        with mock.patch('main.models.User.get_clients',
                        mock_clients.get_clients):
            fs = get_fs(self.user, chunk_size=3, replicas=2)

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
        fs = get_fs(self.user)
        dir = fs.mkdir('/foo')
        self.assertEqual('/foo', dir.path)
        fs.rmdir('/foo')
        with self.assertRaises(DirectoryNotFoundError):
            fs.rmdir('/foo')

    def test_listdir(self):
        fs = get_fs(self.user)
        fs.mkdir('/foo')
        fs.mkdir('/foo/bar')
        fs.mkdir('/foo/baz')

        listing = fs.listdir('/foo')
        self.assertEqual(2, len(listing.dirs))
        self.assertEqual(0, len(listing.files))

        with self.assertRaises(DirectoryNotFoundError):
            fs.listdir('/missing')

    def test_move(self):
        fs = get_fs(self.user)
        fs.mkdir('/foo')
        fs.mkdir('/bar')
        fs.move('/foo', '/bar')

        self.assertFalse(fs.exists('/foo'))
        self.assertTrue(fs.exists('/bar/foo'))
        self.assertTrue(fs.isdir('/bar/foo'))

    def test_move_file(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            # Dst directories are created automatically.
            fs.move('/foo', '/bar')

            self.assertTrue(fs.exists('/bar'))
            self.assertTrue(fs.isfile('/bar'))
            self.assertFalse(fs.exists('/foo'))

    def test_move_fail(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)

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
        fs = get_fs(self.user)
        fs.mkdir('/foo')
        fs.mkdir('/bar')
        fs.copy('/foo', '/bar')

        self.assertTrue(fs.exists('/foo'))
        self.assertTrue(fs.exists('/bar/foo'))
        self.assertTrue(fs.isdir('/foo'))
        self.assertTrue(fs.isdir('/bar/foo'))

    def test_copy_file(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)

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
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            with self.assertRaises(FileConflictError):
                fs.mkdir('/foo')

            fs.mkdir('/bar/foo')

    def test_info(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)

            with self.assertRaises(PathNotFoundError):
                fs.info('/foo')

            with BytesIO(TEST_FILE) as f:
                fs.upload('/foo', f)

            fs.info('/foo')

    def test_is_dir_file(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)
            self.assertTrue(fs.isdir('/'))
            self.assertFalse(fs.isfile('/'))

    def test_file_version(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.user).get_clients):
            fs = get_fs(self.user)

            with BytesIO(TEST_FILE) as f:
                fi = fs.upload('/foo', f)

            with BytesIO(TEST_FILE) as f:
                fi = fs.upload('/foo', f)

            # Two versions of the file should be produced.
            self.assertEqual(2, fi.file.versions.count())

            # Both versions should share chunks
            v1, v2 = fi.file.versions.all()
            self.assertEqual(
                [c.uid for c in v1.chunks.all()],
                [c.uid for c in v2.chunks.all()],
            )


class SharingTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usera = User.objects.create(email='foo@a.org')
        cls.userb = User.objects.create(email='foo@b.org')

    def test_listdir(self):
        with mock.patch('main.models.User.get_clients',
                        MockClients(self.usera).get_clients):
            fsa = get_fs(self.usera)
            with mock.patch('main.models.User.get_clients',
                            MockClients(self.userb).get_clients):
                fsb = get_fs(self.userb)

                # User A creates two directories.
                dira0 = fsa.mkdir('/foo')
                dira1 = fsa.mkdir('/bar')
                # User B creates one.
                dirb0 = fsb.mkdir('/baz')
                # User A then shares them with User B.
                dira0.share(self.userb)
                dira1.share(self.userb, parent=dirb0)

                # Ensure shares were successful.
                self.assertTrue(fsb.isdir(dira0.path))
                self.assertTrue(fsa.exists(dira1.path))
                self.assertTrue(fsb.exists('/baz/bar'))

                listing = fsb.listdir('/')
                self.assertEqual(2, len(listing.dirs))

                # Then User B moves one.
                fsb.move(dira0.path, '/foo-bar')
                self.assertTrue(fsa.exists(dira0.path))
                self.assertTrue(fsb.exists('/foo-bar'))


class GetclientTestCase(TestCase):
    def test_get_client(self):
        with self.assertRaises(ValueError):
            get_client(1024)
