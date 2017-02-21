import redis

from os.path import split as pathsplit

from .base import BaseMetastore
from .. import Chunk
from ..errors import (
    FileNotFoundError, DirectoryNotFoundError, DirectoryNotEmptyError
)


class RedisMetastore(BaseMetastore):
    """
    Low-level API.

    Implements Metastore interface for Redis.

    Stores a file system's namespace in Redis. Does so using a hash for the top
    level directory. Each key in this hash is a directory or file contained
    within. Each value refers to either another hash or a list. If a hash, then
    the item is a directory. If a list, then the item is a file, and the list
    contains it's chunk identifiers.

    Chunks are individual lists that contain the URLs referring to the
    datastores containing replicas of the given chunk.

    Datastore URLs can be used to retrieve a given chunk.
    """

    def __init__(self, ns, host='localhost', port=6379, db=0):
        self.ns = ns
        self._redis = redis.StrictRedis(host=host, port=port, db=db)

    def _key(self, type, name):
        assert isinstance(type, str), 'Type must be string'
        assert isinstance(name, str), 'Name must be string'
        return '{0}:{1}:{2}'.format(self.ns, type, name)

    def _decode(self, value):
        return str(value, 'utf-8')

    def get_file(self, name):
        key = self._key('file', name)
        dname, bname = pathsplit(name)
        dkey = self._key('dir', dname)
        if self._redis.hget(dkey, bname) != b'file':
            raise FileNotFoundError(name)
        # Get all items in the list, these are chunk identifiers.
        chunks = list(map(self._decode, self._redis.lrange(key, 0, -1)))
        chunks = list(map(Chunk.from_string, chunks))
        return chunks

    def del_file(self, name):
        key = self._key('file', name)
        dname, bname = pathsplit(name)
        dkey = self._key('dir', dname)
        self._redis.hdel(dkey, bname)
        while True:
            cname = self._redis.rpoplpush(key, self._key('meta', 'tombstone'))
            if cname is None:
                break
        self._redis.delete(key)

    def put_file(self, name, chunks=[]):
        key = self._key('file', name)
        dname, bname = pathsplit(name)
        dkey = self._key('dir', dname)
        # Adds an item to the hash located at dirname with key of basename, and
        # value of 'file'.
        self._redis.hset(dkey, bname, 'file')
        if chunks:
            self._redis.lpush(key, *map(str, chunks))

    def get_dir(self, name):
        key = self._key('dir', name)
        dname, bname = pathsplit(name)
        dkey = self._key('dir', dname)
        if self._redis.hget(dkey, bname) != b'dir':
            raise DirectoryNotFoundError(name)
        items = self._redis.hgetall(key)
        return {self._decode(k): self._decode(v) for k, v in items.items()}

    def del_dir(self, name):
        key = self._key('dir', name)
        if self._redis.hgetall(key):
            raise DirectoryNotEmptyError(name)
        dname, bname = pathsplit(name)
        dkey = self._key('dir', dname)
        if self._redis.hget(dkey, bname) != b'dir':
            raise DirectoryNotFoundError(name)
        self._redis.hdel(dkey, bname)
        self._redis.delete(key)

    def put_dir(self, name):
        while name != '/':
            dname, bname = pathsplit(name)
            dkey = self._key('dir', dname)
            if self._redis.hget(dkey, bname) == b'file':
                raise FileExistsError(name)
            self._redis.hset(dkey, bname, 'dir')
            name = dname
