import collections
import random
import logging

from io import BytesIO
from hashlib import md5

from django.conf import settings
from django.db import transaction

from main.models import (
    Directory, File, Chunk, ChunkStorage
)


# Default 32K chunk size.
CHUNK_SIZE = 32 * 1024
REPLICAS = 2
LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.StreamHandler())


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


class MulticloudBase(object):
    """
    Base class for interacting with multiple clouds.
    """

    def __init__(self, clouds):
        assert isinstance(clouds, collections.Iterable), \
            'clouds must be iterable'
        self.clouds = clouds

    def get_cloud(self, oauth_access):
        for cloud in self.clouds:
            if cloud.oauth_access == oauth_access:
                return cloud
        raise ValueError('invalid cloud oauth_access')


class FileLikeBase(object):
    """
    Implement File-like methods.

    Implements methods shared by both MulticloudReader and MulticloudWriter.
    """

    def tell(self):
        raise NotImplementedError()

    def seek(self):
        raise NotImplementedError()

    def flush(self):
        pass

    def close(self):
        self._closed = True


class MulticloudReader(MulticloudBase, FileLikeBase):
    """
    File-like object that reads from multiple clouds.
    """
    def __init__(self, user, clouds, file):
        super().__init__(clouds)
        self.user = user
        self.file = file
        self.chunks = list(
            Chunk.objects.filter(
                filechunk__file=file).order_by('filechunk__serial')
        )
        self._buffer = []
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def _read_chunk(self):
        try:
            chunk = self.chunks.pop(0)
        except IndexError:
            raise EOFError('out of chunks')
        for storage in chunk.storage.all():
            cloud = self.get_cloud(storage.storage)
            try:
                return cloud.download(chunk)
            except Exception as e:
                LOGGER.exception(e)
                continue
        raise IOError('could not read chunk')

    def read(self, size=-1):
        """
        Read series of chunks from multiple clouds.
        """
        if self._closed:
            raise ValueError('I/O operation on closed file.')
        if not self.chunks:
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


class MulticloudWriter(MulticloudBase, FileLikeBase):
    """
    File-like object that writes to multiple clouds.
    """
    def __init__(self, user, clouds, file, chunk_size=CHUNK_SIZE,
                 replicas=REPLICAS):
        super().__init__(clouds)
        self.user = user
        self.file = file
        self.chunk_size = chunk_size
        self.replicas = replicas
        self._buffer = []
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def _write_chunk(self, data):
        """
        Write a single chunk.

        Writes chunk to multiple clouds in parallel.
        """
        def _select_clouds():
            clouds = set()
            while len(clouds) < self.replicas:
                clouds.add(random.choice(self.clouds))
            return clouds

        clouds = _select_clouds()
        chunk = Chunk.objects.create(md5=md5(data).hexdigest())
        for cloud in clouds:
            chunk.storage.add(
                ChunkStorage.objects.create(chunk=chunk,
                                            storage=cloud.oauth_access))
            cloud.upload(chunk, data)
        self.file.add_chunk(chunk)

    def write(self, data):
        """
        Write data to multiple clouds.

        Uses a write-through buffer to ensure each chunk is the proper size.
        Close flushes the remainder of the buffer.
        """
        if self._closed:
            raise ValueError('I/O operation on closed file.')
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
        if self._closed:
            return
        self._write_chunk(b''.join(self._buffer))
        super().close()


class MulticloudFilesystem(MulticloudBase):
    def __init__(self, user, chunk_size=settings.CLOUDSTRYPE_CHUNK_SIZE):
        super().__init__(user.get_clients())
        self.user = user
        self.chunk_size = chunk_size
        self.replicas = user.get_option('replicas', 1)
        assert len(self.clouds) >= self.replicas, \
            'not enough clouds (%s) for %s replicas' % (len(self.clouds),
                                                        self.replicas)

    def download(self, path):
        """
        Download from multiple clouds.

        Uses Metastore backend to resolve path to a series of chunks. Returns a
        MulticloudReader that can read these chunks in order.
        """
        file = File.objects.get(path=path, user=self.user)
        return MulticloudReader(self.user, self.clouds, file)

    @transaction.atomic
    def upload(self, path, f):
        """
        Upload to multiple clouds.

        Reads the provided file-like object as a series of chunks, writing each
        to multiple cloud providers. Stores chunk information into the
        Metastore backend.
        """
        file = File.objects.create(path=path, user=self.user)
        with MulticloudWriter(self.user, self.clouds, file,
                              chunk_size=self.chunk_size,
                              replicas=self.replicas) as out:
            for chunk in chunker(f, chunk_size=self.chunk_size):
                out.write(chunk)
        return file

    def delete(self, path):
        """
        Delete from multiple clouds.

        If path is a file it is deleted (as described below). If path is a
        directory then it is simply removed from the Metastore.

        Uses Metastore backend to resolve path to a series of chunks. Deletes
        the chunks from cloud providers and Metastore backend.
        """
        # We do not care about order...
        file = File.objects.get(path=path, user=self.user)
        for chunk in Chunk.objects.filter(filechunk__file=file):
            for storage in chunk.storage.all():
                cloud = self.get_cloud(storage.storage)
                cloud.delete(chunk)
        file.delete()

    def mkdir(self, path):
        return Directory.objects.create(path=path, user=self.user)

    def rmdir(self, path):
        Directory.objects.get(path=path, user=self.user).delete()

    def move(self, src, dst):
        # TODO: simply modify the parent of a file or directory.
        raise NotImplementedError()

    def copy(self, src, dst):
        # TODO: simply clone the file or directory with a new parent. Files
        # can share the same chunks!
        raise NotImplementedError()
