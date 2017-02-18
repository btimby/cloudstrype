import random
import logging

from io import BytesIO
from os.path import split as pathsplit
from hashlib import md5
from urllib.parse import urlparse
from collections import defaultdict

import redis


CLOUDS = {}
CHUNK_SIZE = 128 * 1024
LOGGER = logging.getLogger(__file__)
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.DEBUG)


class InvalidModeError(Exception):
    pass


class FileDoesNotExistError(Exception):
    pass


class Cloud(object):
    def __init__(self, name):
        self.name = name #str(name, 'utf-8')
        self.data = CLOUDS.setdefault(name, {})

    def get_chunk(self, id):
        #id = str(id, 'utf-8')
        return self.data[id]

    def put_chunk(self, id, data):
        self.data[id] = data
        return 'cloud://{0}/{1}'.format(self.name, id)


class Chunk(object):
    def __init__(self, urls):
        self.urls = urls


class ChunkedFile(object):
    def __init__(self, manager, name, mode):
        self.manager = manager
        self.name = name
        self.mode = mode
        self._buffer = BytesIO()
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        if not self._closed:
            self.close()

    def seek(self, pos, whence=0):
        pass

    def close(self):
        pass


class ChunkedFileReader(ChunkedFile):
    def write(self, *args, **kwargs):
        raise NotImplementedError()

    def read(self, size=-1):
        chunks = self.manager.get_file(self.name)
        return self.manager.get_chunk(chunks[0])


class ChunkedFileWriter(ChunkedFile):
    def read(self, *args, **kwargs):
        raise NotImplementedError()

    def _write_chunk(self, data):
        id = md5(data).hexdigest()
        self.manager.put_chunk(id, data)
        self.manager.put_file(self.name, [id])

    def write(self, data):
        self._buffer.write(data)
        if self._buffer.tell() >= CHUNK_SIZE:
            self._buffer.seek(0)
            self._write_chunk(self._buffer.read(CHUNK_SIZE))
            buffer = BytesIO()
            buffer.write(self._buffer.read())
            self._buffer.close()
            self._buffer = buffer

    def close(self):
        if self._closed:
            raise IOError('Already closed')
        self._write_chunk(self._buffer.getvalue())
        self._buffer.close()
        self._closed = True


class BaseMetastore(object):
    pass


class RedisMetastore(BaseMetastore):
    """
    Low-level API.

    Implements metastore interface for Redis.

    Stores a file system's namespace in Redis. Does so using a hash for the top
    level directory. Each key in this hash is a directory or file contained
    within. Each value refers to either another hash or a list. If a hash, then
    the item is a directory. If a list, then the item is a file, and the list
    contains it's chunk identifiers.

    Chunks are individual lists that contain the URLs referring to the
    datastores containing replicas of the given chunk.

    Datastore URLs can be used to retrieve a given chunk.
    """

    def __init__(self, host='localhost', port=6379, db=0):
        self._redis = redis.StrictRedis(host=host, port=port, db=db)

    def _key(self, ns, type, name):
        assert isinstance(ns, str), 'ns must be string'
        assert isinstance(type, str), 'Type must be string'
        assert isinstance(name, str), 'Name must be string'
        return '{0}:{1}:{2}'.format(ns, type, name)

    def _decode(self, value):
        return str(value, 'utf-8')

    def get_file(self, ns, name):
        dname, bname = pathsplit(name)
        if self._redis.hget(self._key(ns, 'dir', dname), bname) != b'file':
            raise FileDoesNotExistError(name)
        # Get all items in the list, these are chunk identifiers.
        return list(map(self._decode, self._redis.lrange(self._key(ns, 'file', name), 0, -1)))

    def del_file(self, ns, name):
        dname, bname = pathsplit(name)
        self._redis.hdel(self._key(ns, 'dir', dname), bname)
        while True:
            cname = self._redis.rpoplpush(self._key(ns, 'file', name),
                                          self._key(ns, 'meta', 'tombstone'))
            if cname is None:
                break
        self._redis.delete(self._key(ns, 'file', name))

    def put_file(self, ns, name, chunks=[]):
        dname, bname = pathsplit(name)
        # Adds an item to the hash located at dirname with key of basename, and
        # value of 'file'.
        self._redis.hset(self._key(ns, 'dir', dname), bname, 'file')
        if chunks:
            self._redis.lpush(self._key(ns, 'file', name), *chunks)

    def get_dir(self, ns, name):
        items = self._redis.hgetall(self._key(ns, 'dir', name))
        return {self._decode(k): self._decode(v) for k, v in items.items()}

    def del_dir(self, ns, name):
        dname, bname = pathsplit(name)
        self._redis.hdel(self._key(ns, 'dir', dname), bname)
        self._redis.delete(self._key(ns, 'dir', name))

    def put_dir(self, ns, name):
        dname, bname = pathsplit(name)
        self._redis.hset(self._key(ns, 'dir', dname), bname, 'dir')

    def get_chunk(self, ns, name):
        return list(map(self._decode, self._redis.lrange(self._key(ns, 'chunk', name), 0, -1)))

    def del_chunk(self, ns, name):
        self._redis.delete(self._key(ns, 'chunk', name))

    def put_chunk(self, ns, name, urls):
        self._redis.lpush(self._key(ns, 'chunk', name), *urls)

    def get_cloud(self, ns):
        return list(map(self._decode, self._redis.lrange(self._key(ns, 'cloud', 'list'), 0, -1)))

    def del_cloud(self, ns):
        self._redis.delete(self._key(ns, 'cloud', 'list'))

    def put_cloud(self, ns, clouds):
        self._redis.lpush(self._key(ns, 'cloud', 'list'), *clouds)


class BaseDatastore(object):
    pass


class CloudDatastore(BaseDatastore):
    def __init__(self, ms, replicas=2):
        assert issubclass(ms.__class__, BaseMetastore), \
            'ms must be metastore instance'
        self.ms = ms
        self.replicas = replicas

    def get_chunk(self, ns, urls):
        for url in urls:
            urlp = urlparse(url)
            cloud = Cloud(urlp.netloc)
            try:
                return cloud.get_chunk(urlp.path.strip('/'))
            except Exception as e:
                LOGGER.debug(e)
                continue
        raise IOError('Could not retrieve chunk')

    def put_chunk(self, ns, id, data):
        urls, r = [], 0
        clouds = list(map(Cloud, self.ms.get_cloud(ns)))
        assert len(clouds) >= self.replicas, 'Cannot satisfy replicas'
        while r < self.replicas:
            # TODO: if we make this predictable, we don't need to store the
            # URLs, we can recreate them when reading.
            i = random.randint(0, len(clouds) - 1)
            cloud = clouds.pop(i)
            urls.append(cloud.put_chunk(id, data))
            r += 1
        return urls


class Manager(object):
    """
    Mid-level API.

    Interacts with both metastore and datastore interfaces.
    """
    def __init__(self, ns, ms, ds):
        assert isinstance(ns, str), 'ns must be string'
        assert issubclass(ms.__class__, BaseMetastore), \
            'ms must be metastore instance'
        assert issubclass(ds.__class__, BaseDatastore), \
            'ds must be datastore instance'
        self.ns = ns
        self.ms = ms
        self.ds = ds

    def get_chunk(self, id):
        urls = self.ms.get_chunk(self.ns, id)
        return self.ds.get_chunk(self.ns, urls)

    def put_chunk(self, id, data):
        urls = self.ds.put_chunk(self.ns, id, data)
        self.ms.put_chunk(self.ns, id, urls)

    def get_file(self, name):
        return self.ms.get_file(self.ns, name)

    def put_file(self, name, chunks=[]):
        self.ms.put_file(self.ns, name, chunks)

    def put_dir(self, name):
        self.ms.put_dir(self.ns, name)

    def get_dir(self, name):
        return sorted(self.ms.get_dir(self.ns, name).keys())


class Filesystem(object):
    """
    High-level API.

    Implements file-system interface.
    """

    def __init__(self, manager):
        self.manager = manager

    def open(self, path, mode):
        if 'r' in mode:
            return ChunkedFileReader(self.manager, path, mode)
        elif 'w' in mode:
            return ChunkedFileWriter(self.manager, path, mode)
        else:
            raise InvalidModeError('Mode must contain (r)ead or (w)rite')

    def remove(self, path):
        self.manager.del_file(path)

    def mkdir(self, path):
        self.manager.put_dir(path)

    def rmdir(self, path):
        self.manager.del_dir(path)

    def ls(self, path):
        return self.manager.get_dir(path)
