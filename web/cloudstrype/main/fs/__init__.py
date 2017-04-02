"""
I would like to remove this to a dedicated async HTTP server.

Upload flow:
 - Upload handled by nginx (written to /tmp).
 - Upload handed off to uWSGI application, which auths users and performs
   validation.
 - Upload handed off to aiohttp server, temp file path passed.
 - Application waits for aiohttp and nginx waits for application.
 - https://www.nginx.com/resources/wiki/modules/upload/

 [User] -> [Nginx] -> [uWSGI] -> [AIOHTTP]
              |                      ^
              |                      |
              +--------[disk]--------+

 Download flow:
 - Download request hits application via nginx.
 - Perform validation and auth.
 - Redirect nginx to aiohttp, which will stream chunks via nginx to caller.
 - https://kovyrin.net/2010/07/24/nginx-fu-x-accel-redirect-remote/

 [User] <- [Nginx] <-> [uWSGI]
              ^
              |
           [AIOHTTP]
"""

import collections
import random
import logging

from io import BytesIO
from os.path import join as pathjoin
from os.path import split as pathsplit
from hashlib import md5, sha1

from django.conf import settings
from django.db import transaction

from main.models import (
    Directory, File, Chunk, ChunkStorage, DirectoryQuerySet
)
from main.fs.raid import chunker, DEFAULT_CHUNK_SIZE
from main.fs.errors import (
    DirectoryNotFoundError, FileNotFoundError, PathNotFoundError,
    DirectoryConflictError, FileConflictError
)


REPLICAS = 2
LOGGER = logging.getLogger(__name__)


DirectoryListing = collections.namedtuple('DirectoryListing',
                                          ('dir', 'dirs', 'files'))


class MulticloudBase(object):
    """
    Base class for interacting with multiple clouds.
    """

    def __init__(self, storage):
        assert isinstance(storage, collections.Iterable), \
            'storage must be iterable'
        self.storage = storage

    def get_storage(self, storage):
        for s in self.storage:
            if s.storage.pk == storage.pk:
                return s
        raise ValueError('invalid storage %s' % storage)


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
    def __init__(self, user, storage, file):
        super().__init__(storage)
        self.user = user
        self.file = file
        self.chunks = list(
            Chunk.objects.filter(
                filechunks__file=file).order_by('filechunks__serial')
        )
        self._buffer = []
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def _read_chunk(self):
        try:
            chunk = self.chunks.pop()
        except IndexError:
            raise EOFError('out of chunks')
        # Try providers in random order.
        for storage in sorted(chunk.storage.all(),
                              key=lambda k: random.random()):
            cloud = self.get_storage(storage.storage)
            try:
                return cloud.download(chunk)
            except Exception as e:
                LOGGER.exception(e)
                continue
        raise IOError('Failed to read chunk')

    def __iter__(self):
        while self.chunks:
            yield self._read_chunk()

    # TODO: refactor this.
    def read(self, size=-1):  # NOQA
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
    def __init__(self, user, clouds, file, chunk_size=DEFAULT_CHUNK_SIZE,
                 replicas=REPLICAS):
        super().__init__(clouds)
        self.user = user
        self.file = file
        self.chunk_size = chunk_size
        self.replicas = replicas
        self._md5 = md5()
        self._sha1 = sha1()
        self._size = 0
        self._buffer = []
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def _write_chunk(self, data):
        """
        Write a single chunk.

        Writes chunk to multiple clouds.
        """
        # Upload to N random providers where N is desired replica count.
        chunk = Chunk.objects.create(md5=md5(data).hexdigest())
        chunks_uploaded = 0
        for storage in sorted(self.storage, key=lambda k: random.random()):
            # We add one to replicas because replicas are the COPIES we write
            # in addition to the base block.
            if chunks_uploaded == self.replicas + 1:
                break
            try:
                storage.upload(chunk, data)
            except Exception as e:
                LOGGER.exception(e)
                continue
            chunk.storage.add(
                ChunkStorage.objects.create(chunk=chunk,
                                            storage=storage.storage))
            chunks_uploaded += 1
        else:
            raise IOError('Failed to write chunk')
        self.file.add_chunk(chunk)

    def write(self, data):
        """
        Write data to multiple clouds.

        Uses a write-through buffer to ensure each chunk is the proper size.
        Close flushes the remainder of the buffer.
        """
        if self._closed:
            raise ValueError('I/O operation on closed file.')
        self._size += len(data)
        self._md5.update(data)
        self._sha1.update(data)
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
        # Update content related attributes.
        self.file.size = self._size
        self.file.md5 = self._md5.hexdigest()
        self.file.sha1 = self._sha1.hexdigest()
        # Flush to db.
        self.file.save()
        super().close()


class MulticloudFilesystem(MulticloudBase):
    def __init__(self, user, chunk_size=settings.CLOUDSTRYPE_CHUNK_SIZE,
                 replicas=0):
        super().__init__(user.get_clients())
        self.user = user
        self.chunk_size = chunk_size
        self.level = user.get_option('raid_level', 0)
        self.replicas = user.get_option('raid_replicas', replicas)
        self._ensure_root()

    def _ensure_root(self):
        # Do this upfront so that fs operations can assume that a root
        # directory exists.
        root, _ = Directory.objects.get_or_create(user=self.user, path='/',
                                                  display_path='/')

    def download(self, path):
        """
        Download from multiple storage.

        Uses Metastore backend to resolve path to a series of chunks. Returns a
        MulticloudReader that can read these chunks in order.
        """
        try:
            file = File.objects.get(path=path, user=self.user)
        except File.DoesNotExist:
            raise FileNotFoundError(path)
        return MulticloudReader(self.user, self.storage, file)

    @transaction.atomic
    def upload(self, path, f):
        """
        Upload to multiple storage.

        Reads the provided file-like object as a series of chunks, writing each
        to multiple cloud providers. Stores chunk information into the
        Metastore backend.
        """
        assert len(self.storage) >= self.replicas, \
            'not enough storage (%s) for %s replicas' % (len(self.storage),
                                                         self.replicas)

        file = File.objects.create(path=path, user=self.user)
        with MulticloudWriter(self.user, self.storage, file,
                              chunk_size=self.chunk_size,
                              replicas=self.replicas) as out:
            for chunk in chunker(f, chunk_size=self.chunk_size):
                out.write(chunk)
        return file

    @transaction.atomic
    def delete(self, path):
        """
        Delete from multiple storage.

        If path is a file it is deleted (as described below). If path is a
        directory then it is simply removed from the Metastore.

        Uses Metastore backend to resolve path to a series of chunks. Deletes
        the chunks from cloud providers and Metastore backend.
        """
        try:
            file = File.objects.get(path=path, user=self.user)
        except File.DoesNotExist:
            raise FileNotFoundError(path)
        # We do not care about order...
        for chunk in Chunk.objects.filter(filechunks__file=file):
            for storage in chunk.storage.all():
                cloud = self.get_storage(storage.storage)
                try:
                    cloud.delete(chunk)
                except Exception as e:
                    LOGGER.exception(e)
                    continue
        file.delete()

    def mkdir(self, path):
        if self.isfile(path):
            raise FileConflictError(path)
        return Directory.objects.create(path=path, user=self.user)

    def rmdir(self, path):
        try:
            Directory.objects.get(path=path, user=self.user).delete()
        except Directory.DoesNotExist:
            raise DirectoryNotFoundError(path)

    @transaction.atomic
    def _move_file(self, file, dst):
        if self.isdir(dst):
            raise DirectoryConflictError(dst)
        dst, file.name = pathsplit(dst)
        try:
            file.directory = \
                Directory.objects.get(path=dst, user=self.user)
        except Directory.DoesNotExist:
            raise DirectoryNotFoundError(dst)
        file.save()
        return file

    @transaction.atomic
    def _move_dir(self, dir, dst):
        if self.isfile(dst):
            raise DirectoryConflictError(dst)
        try:
            dir.parent = \
                Directory.objects.get(path=dst, user=self.user)
        except Directory.DoesNotExist:
            raise DirectoryNotFoundError(dst)
        kwargs = {
            'path': pathjoin(dst, dir.name),
        }
        DirectoryQuerySet._args(kwargs)
        for name, value in kwargs.items():
            setattr(dir, name, value)
        dir.save()
        return dir

    @transaction.atomic
    def move(self, src, dst):
        try:
            file = File.objects.get(path=src, user=self.user)
            return self._move_file(file, dst)
        except File.DoesNotExist:
            pass
        try:
            dir = Directory.objects.get(path=src, user=self.user)
            return self._move_dir(dir, dst)
        except Directory.DoesNotExist:
            pass
        raise PathNotFoundError(src)

    @transaction.atomic
    def _copy_file(self, srcfile, dst):
        if self.isdir(dst):
            dst = pathjoin(dst, srcfile.name)
        if self.isfile(dst):
            raise FileConflictError(dst)
        # Clone file first.
        dstfile = \
            File.objects.create(md5=srcfile.md5, path=dst, user=self.user)
        # Then clone it's chunks:
        for chunk in Chunk.objects.filter(filechunks__file=srcfile).order_by(
                                          'filechunks__serial'):
            dstfile.add_chunk(chunk)
        return dstfile

    @transaction.atomic
    def _copy_dir(self, srcdir, dst):
        if self.isdir(dst):
            dst = pathjoin(dst, srcdir.name)
        if self.isfile(dst):
            raise FileConflictError(dst)
        # Clone dir first.
        dstdir = Directory.objects.create(path=dst, user=self.user)
        # Then copy children recursively.
        _, dirs, files = self.listdir(srcdir.path, dir=srcdir)
        for subdir in dirs:
            self._copy_dir(subdir, dstdir.path)
        for subfile in files:
            self._copy_file(subfile, dstdir.path)
        return dstdir

    @transaction.atomic
    def copy(self, src, dst):
        try:
            file = File.objects.get(path=src, user=self.user)
            return self._copy_file(file, dst)
        except File.DoesNotExist:
            pass
        try:
            dir = Directory.objects.get(path=src, user=self.user)
            return self._copy_dir(dir, dst)
        except Directory.DoesNotExist:
            pass
        raise PathNotFoundError('src')

    def listdir(self, path, dir=None):
        if dir is None:
            try:
                dir = Directory.objects.get(path=path, user=self.user)
            except Directory.DoesNotExist:
                raise DirectoryNotFoundError(path)
        return DirectoryListing(
            dir, Directory.objects.filter(parent=dir, user=self.user),
            File.objects.filter(directory=dir, user=self.user)
        )

    def info(self, path, file=None):
        if file is None:
            try:
                file = File.objects.get(path=path, user=self.user)
            except File.DoesNotExist:
                raise FileNotFoundError(path)
        return file

    def isdir(self, path):
        return Directory.objects.filter(path=path, user=self.user).exists()

    def isfile(self, path):
        return File.objects.filter(path=path, user=self.user).exists()

    def exists(self, path):
        return self.isdir(path) or self.isfile(path)
