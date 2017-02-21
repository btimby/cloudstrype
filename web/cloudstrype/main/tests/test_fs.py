from io import BytesIO
from os.path import split as pathsplit

from django.test import TestCase

from mockredis import MockRedis

from main.fs.async import chunker
from main.fs.async import Chunk
from main.fs.async.errors import (
    FileNotFoundError, DirectoryNotFoundError, DirectoryNotEmptyError
)
from main.fs.async.cloud.base import BaseProvider
from main.fs.async.metadata.redis import RedisMetastore
from main.fs.async import MulticloudManager


class DummyProvider(BaseProvider):
    """
    "Cloud" provider that stores file data in a dictionary.
    """
    def __init__(self, id):
        self.id = '%04x' % id
        self.data = {}

    async def download(self, id):
        return self.data.get(id)

    async def upload(self, id, data):
        self.data[id] = data

    async def delete(self, id):
        self.data.pop(id)


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

    TEST_CHUNK_ID = '0001:acbd18db4cc2f85cedef654fccc4a4d8'

    def test_chunk(self):
        chunk = Chunk.from_string(self.TEST_CHUNK_ID)
        self.assertEqual(['0001'], chunk.clouds)
        self.assertEqual('acbd18db4cc2f85cedef654fccc4a4d8', chunk.id)
        self.assertEqual(self.TEST_CHUNK_ID, str(chunk))

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
        # Create a manager with three dummy clouds. And a dummy metastore.
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
        self.mc.upload('foobar.txt', f)

        # Test download.
        contents = yield from self.mc.download('foobar.txt').read()
        self.assertEqual(self.TEST_SMALL_FILE, contents)

        # Test delete.
        self.mc.delete('foobar.txt')
        with self.assertRaises(FileNotFoundError):
            self.mc.download('foobar.txt').read()

    def test_delete(self):
        with self.assertRaises(FileNotFoundError):
            self.mc.delete('/barfoo')

        self.mc.create('/bar/foo')

        with self.assertRaises(DirectoryNotEmptyError):
            self.mc.delete('/bar')
