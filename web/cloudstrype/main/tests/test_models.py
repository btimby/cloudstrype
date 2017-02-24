from django.test import TestCase


from main.models import (
    User, File, Directory, Chunk, FileChunk
)


class DirectoryTestCase(TestCase):
    def test_create(self):
        user = User.objects.create(email='foo@bar.org')

        with self.assertRaises(ValueError):
            Directory.objects.create(path='/foobar')

        dir1 = Directory.objects.create(path='/foobar', user=user)
        self.assertEqual('/foobar', dir1.path)

        dir2 = Directory.objects.create(path='/foobar/foo/bar', user=user)
        self.assertEqual('/foobar/foo/bar', dir2.path)

        dir1.delete()


class FileTestCase(TestCase):
    def test_create(self):
        user = User.objects.create(email='foo@bar.org')

        with self.assertRaises(ValueError):
            File.objects.create(path='/foo/bar')

        dir1 = Directory.objects.create(path='/foo', user=user)
        File.objects.create(path='/foo/bar', user=user)

        dir1.delete()

    def test_chunks(self):
        user = User.objects.create(email='foo@bar.org')
        file = File.objects.create(
            path='/foo/bar', user=user,
            directory=Directory.objects.create(path='/foo', user=user))

        chunk1 = Chunk.objects.create()
        chunk2 = Chunk.objects.create()
        file.add_chunk(chunk1)

        self.assertTrue(
            FileChunk.objects.filter(file=file, chunk=chunk1).exists())

        file.add_chunk(chunk2)

        self.assertEqual(2, FileChunk.objects.filter(file=file).count())

        for i, chunk in enumerate(FileChunk.objects.filter(
                                  file=file).order_by('serial')):
            self.assertEqual(i + 1, chunk.serial)

        file.delete()