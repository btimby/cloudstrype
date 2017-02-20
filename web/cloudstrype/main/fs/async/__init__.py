import asyncio
import collections
import random

from io import BytesIO
from hashlib import md5

from cloud.base import BaseProvider


# Default 32K chunk size.
CHUNK_SIZE = 32 * 1024
REPLICAS = 2


def chunker(f, chunk_size=CHUNK_SIZE):
    """
    Iterator that reads a file-like object and yields a series of chunks.
    """
    while True:
        chunk = f.read(chunk_size)
        if not chunk:
            return
        assert len(chunk) <= chunk_size, 'chunk exceeds %s' % chunk_size
        yield chunk


def execute_futures(futures):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.gather(futures))
    loop.close()


class Chunk(object):
    """
    Class that represents a chunk and the clouds it resides within.

    Clouds is a list of cloud ids that contain this chunk. If the chunk does
    not have data, it is acceptable to pass None. However, an id must be
    provided in that case.

    A chunk can be instantiated using from_string() which reverses the string
    created by __str__(). In this case, the chunk is dataless.
    """

    def __init__(self, clouds, data, id=None):
        assert isinstance(clouds, collections.Iterable), \
            'clouds must be iterable'
        for cloud in clouds:
            assert isinstance(cloud, str), 'clouds must be strings'
        self.clouds = clouds
        if id is None:
            id = md5(chunk).hexdigest()
        self.id = id
        self.data = data

    def __str__(self):
        ids = []
        for cloud in self.clouds:
            ids.append('%s:%s' % (cloud.id, self.id))
        return ','.join(ids)

    @classmethod
    def from_string(self, s):
        clouds = []
        for cloud_chunk in s.split(','):
            cloud_id, _, chunk_id = cloud_chunk.partition(':')
            clouds.append(cloud_id)
        return Chunk(clouds, None, id=chunk_id)


class MulticloudBase(object):
    """
    Base class for interacting with multiple clouds.
    """

    def __init__(self, clouds):
        assert isinstance(clouds, collections.Iterable), \
            'clouds must be iterable'
        for cloud in clouds:
            assert isinstance(cloud, BaseProvider), \
                'clouds must derive from BaseProvider'
        self.clouds = clouds

    def get_cloud(self, id):
        for cloud in self.clouds:
            if cloud.id == id:
                return cloud
        raise ValueError('invalid cloud id')


class MulticloudReader(MulticloudBase):
    """
    File-like object that reads from multiple clouds.
    """
    def __init__(self, clouds, chunks):
        super().__init__(clouds)
        self._chunks = chunks
        self._buffer = []

    def _read_chunk(self):
        try:
            chunk = self._chunks.pop()
        except IndexError:
            raise EOFError('out of chunks')
        for cloud_id in chunk.clouds:
            cloud = self.get_cloud(cloud_id)
            try:
                return cloud.download(chunk.id)
            except:
                pass
        raise IOError('could not read chunk')

    def read(self, size=-1):
        """
        Read series of chunks from multiple clouds.
        """
        if not self._chunks:
            return
        if size == -1:
            # If we have a buffer, return it, otherwise, return the next full
            # chunk.
            if self._buffer:
                data = b''.join(self._buffer)
                self._buffer.clear()
                return data
            else:
                return self._read_chunk()
        else:
            # Fetch chunks until we can satisfy the read or until we are out of
            # chunks.
            while True:
                buffer_len = sum(map(len, self._buffer))
                if buffer_len >= size:
                    break
                try:
                    self._buffer.append(self._read_chunk())
                except EOFError:
                    break
            # Satisfy the read from our buffer. Retain the remainder (if any)
            # for the next read().
            bytes_needed, buff = size, BytesIO()
            # Grab data from our buffer until we have exactly self.chunk_size
            # in our send buffer.
            while bytes_needed and self._buffer:
                head_len = len(self._buffer[0])
                if head_len <= bytes_needed:
                    # Head can be consumed in full, it will not exceed
                    # self.chunk_size
                    buff.write(self._buffer.pop())
                    bytes_needed -= head_len
                else:
                    # Head of our buffer is too large, we need a portion of it.
                    buff.write(self._buffer[0][:bytes_needed])
                    self._buffer[0] = self._buffer[0][bytes_needed:]
                    bytes_needed = 0
            return buff.getvalue()


class MulticloudWriter(MulticloudBase):
    """
    File-like object that writes to multiple clouds.
    """
    def __init__(self, clouds, chunk_size=CHUNK_SIZE):
        super().__init__(clouds)
        self._buffer = []

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def _write_chunk(self, chunk):
        """
        Write a single chunk.

        Writes to multiple clouds in parallel.
        """
        def _select_clouds():
            clouds = set()
            while len(clouds) < replicas:
                clouds.add(random.choice(self.clouds))
            return clouds

        clouds = _select_clouds()
        chunk = Chunk([cloud.id for cloud in clouds], chunk)
        futures = [
            cloud.upload(chunk.id, chunk.data)
            for cloud in clouds
        ]
        execute_futures(futures)
        self.ms.put_file(path, chunks=[chunk])

    def write(self, data, replicas=REPLICAS):
        """
        Write a chunk to multiple clouds.

        Uses a write-through buffer to ensure each chunk is the proper size.
        Close will flush the remainder of the buffer.
        """
        self._buffer.append(data)
        # Write chunks until our buffer is < self.chunk_size.
        while True:
            buffer_len = sum(map(len, self._buffer))
            if buffer_len < self.chunk_size:
                # Buffer does not contain a full chunk.
                break
            # Buffer contains at least one full chunk.
            bytes_needed, buff = self.chunk_size, BytesIO()
            # Grab data from our buffer until we have exactly self.chunk_size
            # in our send buffer.
            while bytes_needed and self._buffer:
                head_len = len(self._buffer[0])
                if head_len <= bytes_needed:
                    # Head can be consumed in full, it will not exceed
                    # self.chunk_size
                    buff.write(self._buffer.pop())
                    bytes_needed -= head_len
                else:
                    # Head of our buffer is too large, we need a portion of it.
                    buff.write(self._buffer[0][:bytes_needed])
                    self._buffer[0] = self._buffer[0][bytes_needed:]
                    bytes_needed = 0
            # We now have a full chunk, send it.
            self._write_chunk(buff.getvalue())

    def close(self):
        """
        Flush remaining buffer and disable writing.
        """
        if self._buffer.closed:
            return
        self._write_chunk(b''.join(self._buffer))
        self._buffer.close()


class MulticloudManager(MulticloudBase):
    def __init__(self, clouds, meta):
        super().__init__(clouds)
        self.meta = meta

    def download(self, path):
        """
        Download from multiple clouds.

        Uses Metastore backend to resolve path to a series of chunks. Returns a
        MulticloudReader that can read these chunks in order.
        """
        chunks = self.meta.get_file(path)
        return MulticloudReader(self.clouds, chunks)

    def upload(self, path, file, replicas=None):
        """
        Upload to multiple clouds.

        Reads the provided file-like object into a series of chunks, writing
        each to multiple cloud providers. Stores chunk information into the
        Metastore backend.
        """
        with MulticloudWriter(self.clouds) as out:
            for chunk in chunker(file):
                out.write(chunk)
        self.meta.put_file(path)

    def delete(self, path):
        """
        Delete from multiple clouds.

        Uses Metastore backend to resolve path to a series of chunks. Deletes
        the chunks from cloud providers and Metastore backend.
        """
        futures = []
        for chunk in self.meta.get_file(path):
            for cloud in chunk.clouds:
                futures.append(cloud.delete(chunk_id))
        execute_futures(futures)
        self.meta.del_file(path)
