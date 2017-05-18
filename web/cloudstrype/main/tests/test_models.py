import time

from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase

from main.models import (
    User, File, Directory, Chunk, FileChunk, Option, BaseStorage,
    OAuth2UserStorage, ArrayStorage, OAuth2Storage, BasicStorage,
    ArrayUserStorage, BasicUserStorage, ChunkStorage,
)
from main.fs.clouds.base import BaseOAuth2APIClient
from main.fs.array import ArrayClient


class DirectoryTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(email='foo@bar.org')

    def test_create(self):
        with self.assertRaises(ValueError):
            Directory.objects.create(path='/foobar')

        dir1 = Directory.objects.create(path='/foobar', user=self.user)
        self.assertEqual('/foobar', dir1.path)
        self.assertTrue(str(dir1).startswith('<'))
        self.assertTrue(str(dir1).endswith('>'))

        dir2 = Directory.objects.create(path='/foobar/foo/bar', user=self.user)
        self.assertEqual('/foobar/foo/bar', dir2.path)

        dir1.delete()


class FileTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create(email='foo@bar.org')

    def test_create(self):
        with self.assertRaises(ValueError):
            File.objects.create(path='/foo/bar')

        dir1 = Directory.objects.create(path='/foo', user=self.user)
        file1 = File.objects.create(path='/foo/bar.txt', user=self.user)

        self.assertEqual(dir1, Directory.objects.get(uid=dir1.uid))
        self.assertEqual(file1, File.objects.get(uid=file1.uid))

        self.assertEqual('.txt', file1.extension)
        self.assertTrue(str(file1).startswith('<'))
        self.assertTrue(str(file1).endswith('>'))

        self.assertEqual(1, Directory.objects.all().count())
        self.assertEqual(1, File.objects.all().count())

        dir1.delete()

        self.assertEqual(0, Directory.objects.all().count())
        self.assertEqual(0, File.objects.all().count())

    def test_chunks(self):
        file = File.objects.create(
            path='/foo/bar', user=self.user,
            parent=Directory.objects.create(path='/foo', user=self.user))

        chunk1 = Chunk.objects.create()
        chunk2 = Chunk.objects.create()
        filechunk1 = file.add_chunk(chunk1)

        self.assertTrue(str(chunk1).startswith('<'))
        self.assertTrue(str(chunk1).endswith('>'))

        self.assertTrue(str(filechunk1).startswith('<'))
        self.assertTrue(str(filechunk1).endswith('>'))

        storage = BaseStorage.objects.create(
            provider=BaseStorage.PROVIDER_DROPBOX)
        oauth2 = OAuth2UserStorage.objects.create(storage=storage,
                                                  user=self.user)
        chunk1storage = ChunkStorage.objects.create(chunk=chunk1,
                                                    storage=oauth2)

        self.assertEqual('<', str(chunk1storage)[0])
        self.assertEqual('>', str(chunk1storage)[-1])

        self.assertTrue(
            FileChunk.objects.filter(file=file, chunk=chunk1).exists())

        file.add_chunk(chunk2)

        self.assertEqual(2, FileChunk.objects.filter(file=file).count())

        for i, chunk in enumerate(FileChunk.objects.filter(
                                  file=file).order_by('serial')):
            self.assertEqual(i + 1, chunk.serial)

        file.delete()


class UserTestCase(TestCase):
    def test_create(self):
        user = User.objects.create_user('foo@bar.org', full_name='Foo Bar')
        self.assertEqual(False, user.is_admin)
        self.assertEqual(False, user.is_staff)
        self.assertEqual('Foo', user.first_name)

        self.assertTrue(str(user).startswith('<'))
        self.assertTrue(str(user).endswith('>'))

        # http://stackoverflow.com/questions/21458387/transactionmanagementerror-you-cant-execute-queries-until-the-end-of-the-atom  # noqa
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                User.objects.create_user('foo@bar.org')

        superuser = User.objects.create_superuser('bar@foo.org', 'foobar',
                                                  full_name='Bar Foo')
        self.assertTrue(superuser.is_admin)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.has_perm('any_perm'))
        self.assertTrue(superuser.has_module_perms('any_app'))
        self.assertEqual('Bar', superuser.first_name)
        self.assertEqual('Bar Foo', superuser.get_full_name())
        self.assertEqual('Bar', superuser.get_short_name())

    def test_fail(self):
        with self.assertRaises(ValueError):
            User.objects.create_user('')

    def test_options(self):
        user = User.objects.create_user('foo@bar.org', full_name='Foo Bar')
        options = Option.objects.create(user=user)

        self.assertEqual('<', str(options)[0])
        self.assertEqual('>', str(options)[-1])


class UserStorageTestCase(TestCase):
    """
    Test user storage (usable storage instances).
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('foo@bar.org',
                                            full_name='Foo Bar')

    def test_oauth2(self):
        storage = BaseStorage.objects.create(
            provider=BaseStorage.PROVIDER_DROPBOX)

        self.assertTrue(str(storage).startswith('<'))
        self.assertTrue(str(storage).endswith('>'))

        oauth2 = OAuth2UserStorage.objects.create(storage=storage,
                                                  user=self.user)

        self.assertTrue(str(oauth2).startswith('<'))
        self.assertTrue(str(oauth2).endswith('>'))

        kwargs = {
            'access_token': 'AAAA',
            'refresh_token': 'BBBB',
            'expires_in': 10,
        }
        oauth2.update(**kwargs)
        self.assertEqual('AAAA', oauth2.access_token)
        self.assertEqual('BBBB', oauth2.refresh_token)
        oauth2.update('CCCC', expires_at=time.time())
        d = oauth2.to_dict()
        self.assertEqual('CCCC', d['access_token'])
        self.assertEqual('BBBB', d['refresh_token'])

    def test_array(self):
        storage = BaseStorage.objects.create(
            provider=BaseStorage.PROVIDER_ARRAY)

        array = ArrayUserStorage.objects.create(storage=storage,
                                                user=self.user)

        self.assertTrue(str(array).startswith('<'))
        self.assertTrue(str(array).endswith('>'))

        # Name should have usable default (is system-provided).
        self.assertIsNotNone(array.name)

        obj = array.get_client()
        self.assertIsInstance(obj, ArrayClient)

    def test_basic(self):
        storage = BaseStorage.objects.create(
            provider=BaseStorage.PROVIDER_BASIC)

        basic = BasicUserStorage.objects.create(storage=storage,
                                                user=self.user,
                                                url='http://foobar.org/',
                                                username='foo',
                                                password='bar')

        self.assertTrue(str(basic).startswith('<'))
        self.assertTrue(str(basic).endswith('>'))

        obj = basic.get_client()
        # Not yet implemented, stub test.
        self.assertIsNone(obj)


class StorageTestCase(TestCase):
    """
    Test storage types.
    """

    def test_array(self):
        storage = ArrayStorage.objects.create(
            provider=BaseStorage.PROVIDER_ARRAY)

        self.assertTrue(str(storage).startswith('<'))
        self.assertTrue(str(storage).endswith('>'))

        with self.assertRaises(NotImplementedError):
            storage.get_client()

    def test_oauth2(self):
        storage = OAuth2Storage.objects.create(
            provider=BaseStorage.PROVIDER_DROPBOX, client_id='id',
            client_secret='secret')

        self.assertTrue(str(storage).startswith('<'))
        self.assertTrue(str(storage).endswith('>'))

        obj = storage.get_client('https://redirect.org/')
        self.assertIsInstance(obj, BaseOAuth2APIClient)

    def test_basic(self):
        storage = BasicStorage.objects.create(
            provider=BaseStorage.PROVIDER_BASIC)

        self.assertTrue(str(storage).startswith('<'))
        self.assertTrue(str(storage).endswith('>'))

        with self.assertRaises(NotImplementedError):
            storage.get_client()
