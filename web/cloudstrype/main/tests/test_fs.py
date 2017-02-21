from io import BytesIO
from os.path import split as pathsplit

from django.test import TestCase

from mockredis import MockRedis

from main.fs.async import chunker
from main.fs.async import Chunk
from main.fs.async.errors import (
    FileNotFoundError, DirectoryNotFoundError, DirectoryNotEmptyError
)
from main.fs.async import MulticloudManager
from main.fs.async.cloud.base import BaseProvider
from main.fs.async.metadata.redis import RedisMetastore


class DummyProvider(BaseProvider):
    """
    "Cloud" provider that stores file data in a dictionary.
    """
    def __init__(self, id):
        self.id = '%04x' % id
        self.data = {}

    async def download(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        return self.data.get(chunk.id)

    async def upload(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        self.data[chunk.id] = chunk.data

    async def delete(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        self.data.pop(chunk.id)


class DummyMetastore(RedisMetastore):
    """
    Metastore that uses mock redis client.
    """
    def __init__(self, ns):
        self.ns = ns
        self._redis = MockRedis()


class FSTestCase(TestCase):
    """
    Test ancillary functions.
    """

    # A chunk id consists of a cloud instance ID (as hex) and an MD5 sum of
    # the chunk itself.
    TEST_CHUNK_ID = '{"id": "acbd18db4cc2f85cedef654fccc4a4d8", "clouds": {"0001": null}}'

    def test_chunk(self):
        chunk = Chunk.from_string(self.TEST_CHUNK_ID)
        self.assertEqual({'0001': None}, chunk.clouds)
        self.assertEqual('acbd18db4cc2f85cedef654fccc4a4d8', chunk.id)

    def test_chunker(self):
        f = BytesIO()
        f.write(b'Peter Piper picked a peck of pickled peppers')
        f.seek(0)
        for chunk in chunker(f, 4):
            self.assertEqual(4, len(chunk))


class MCTestCase(TestCase):
    """
    Test MulticloudManager.
    """

    TEST_SMALL_FILE = b'This is a small test file.'

    def setUp(self):
        # Create a manager with three dummy clouds and a dummy metastore. This
        # excersizes all of the code except that which connects to external
        # resources. That code is tested separately with mocks.
        self.mc = MulticloudManager(
            [
                DummyProvider(1), DummyProvider(2),
                DummyProvider(3), DummyProvider(4)
            ],
            DummyMetastore('test'),
            chunk_size=8,
            replicas=3
        )

    def test_up_down_delete(self):
        # Test upload.
        f = BytesIO(self.TEST_SMALL_FILE)
        yield from self.mc.upload('foobar.txt', f)

        # Test download.
        f = yield from self.mc.download('foobar.txt')
        contents = f.read()
        self.assertEqual(self.TEST_SMALL_FILE, contents)

        # Should raise if read() after close()
        f.close()
        with self.assertRaises(ValueError):
            f.read()

        # Test delete.
        yield from self.mc.delete('foobar.txt')
        with self.assertRaises(FileNotFoundError):
            yield from self.mc.download('foobar.txt')

    def test_delete(self):
        with self.assertRaises(FileNotFoundError):
            yield from self.mc.delete('/barfoo')

        yield from self.mc.create('/bar/foo')

        with self.assertRaises(DirectoryNotEmptyError):
            yield from self.mc.delete('/bar')
