import time

from django.db import transaction
from django.db.utils import IntegrityError
from django.test import TestCase

from main.models import (
    User, File, Directory, Chunk, FileChunk, Option, OAuth2Provider,
    OAuth2AccessToken, OAuth2StorageToken
)


class DirectoryTestCase(TestCase):
    def test_create(self):
        user = User.objects.create(email='foo@bar.org')

        with self.assertRaises(ValueError):
            Directory.objects.create(path='/foobar')

        dir1 = Directory.objects.create(path='/foobar', user=user)
        self.assertEqual('/foobar', dir1.path)
        self.assertEqual('<', str(dir1)[0])
        self.assertEqual('>', str(dir1)[-1])

        dir2 = Directory.objects.create(path='/foobar/foo/bar', user=user)
        self.assertEqual('/foobar/foo/bar', dir2.path)

        dir1.delete()


class FileTestCase(TestCase):
    def test_create(self):
        user = User.objects.create(email='foo@bar.org')

        with self.assertRaises(ValueError):
            File.objects.create(path='/foo/bar')

        dir1 = Directory.objects.create(path='/foo', user=user)
        file1 = File.objects.create(path='/foo/bar.txt', user=user)

        self.assertEqual(dir1, Directory.objects.get(uid=dir1.uid))
        self.assertEqual(file1, File.objects.get(uid=file1.uid))

        self.assertEqual('.txt', file1.extension)
        self.assertEqual('<', str(file1)[0])
        self.assertEqual('>', str(file1)[-1])

        self.assertEqual(2, Directory.objects.all().count())
        self.assertEqual(1, File.objects.all().count())

        dir1.delete()

        self.assertEqual(1, Directory.objects.all().count())
        self.assertEqual(0, File.objects.all().count())

    def test_chunks(self):
        user = User.objects.create(email='foo@bar.org')
        file = File.objects.create(
            path='/foo/bar', user=user,
            directory=Directory.objects.create(path='/foo', user=user))

        chunk1 = Chunk.objects.create()
        chunk2 = Chunk.objects.create()
        filechunk1 = file.add_chunk(chunk1)

        self.assertEqual('<', str(chunk1)[0])
        self.assertEqual('>', str(chunk1)[-1])

        self.assertEqual('<', str(filechunk1)[0])
        self.assertEqual('>', str(filechunk1)[-1])

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

        self.assertEqual('<', str(user)[0])
        self.assertEqual('>', str(user)[-1])

        # http://stackoverflow.com/questions/21458387/transactionmanagementerror-you-cant-execute-queries-until-the-end-of-the-atom  # noqa
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                User.objects.create_user('foo@bar.org')

        superuser = User.objects.create_superuser('bar@foo.org', 'foobar',
                                                  full_name='Bar Foo')
        self.assertEqual(True, superuser.is_admin)
        self.assertEqual(True, superuser.is_staff)
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


class TokenTestCase(TestCase):
    def test_create(self):
        user = User.objects.create_user('foo@bar.org', full_name='Foo Bar')
        provider = OAuth2Provider.objects.create(
            provider=OAuth2Provider.PROVIDER_AMAZON)

        self.assertFalse(provider.is_storage)

        self.assertEqual('<', str(provider)[0])
        self.assertEqual('>', str(provider)[-1])

        token = OAuth2AccessToken.objects.create(provider=provider, user=user)

        self.assertEqual('<', str(token)[0])
        self.assertEqual('>', str(token)[-1])

        kwargs = {
            'access_token': 'AAAA',
            'refresh_token': 'BBBB',
            'expires_in': 10,
        }
        token.update(**kwargs)
        self.assertEqual('AAAA', token.access_token)
        self.assertEqual('BBBB', token.refresh_token)
        token.update('CCCC', expires_at=time.time())
        d = token.to_dict()
        self.assertEqual('CCCC', d['access_token'])
        self.assertEqual('BBBB', d['refresh_token'])

        storage = OAuth2StorageToken(user=user, token=token)

        self.assertEqual('<', str(storage)[0])
        self.assertEqual('>', str(storage)[-1])
