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
from os.path import (
    dirname, basename
)
from hashlib import md5, sha1
from zlib import crc32 as _crc32

from django.conf import settings
from django.db import transaction

from main.models import (
    UserDir, UserFile, File, Chunk, ChunkStorage, UserDirQuerySet, Version,
    FileVersion,
)
from main.fs.raid import chunker, DEFAULT_CHUNK_SIZE
from main.fs.errors import (
    DirectoryNotFoundError, FileNotFoundError, PathNotFoundError,
    DirectoryConflictError, FileConflictError
)


REPLICAS = 2
LOGGER = logging.getLogger(__name__)


def twos_complement(input_value, num_bits):
    """Calculate two's complement integer from the given input value's bits."""
    mask = 2 ** (num_bits - 1)
    return -(input_value & mask) + (input_value & ~mask)


def crc32(data):
    return twos_complement(_crc32(data), 32)


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
    def __init__(self, user, storage, version):
        super().__init__(storage)
        self.user = user
        self.version = version
        self.chunks = list(
            Chunk.objects.filter(
                filechunks__version=version).order_by('filechunks__serial')
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
                data = cloud.download(chunk)
                assert len(data) == chunk.size, 'Size mismatch'
                assert crc32(data) == chunk.crc32, 'CRC32 mismatch'
                return data
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
    def __init__(self, user, clouds, version, chunk_size=DEFAULT_CHUNK_SIZE,
                 replicas=REPLICAS):
        super().__init__(clouds)
        self.user = user
        self.version = version
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
        kwargs = {
            'crc32': crc32(data),
            'md5': md5(data).hexdigest(),
            'size': len(data),
        }
        # Reuse a chunk if one exists.
        try:
            chunk = Chunk.objects.get(**kwargs)
            # All that is left to do is to add this chunk to the version.
        except Chunk.DoesNotExist:
            chunk = Chunk.objects.create(**kwargs)

            # Upload to N random providers where N is desired replica count.
            chunks_uploaded = 0
            for storage in sorted(self.storage, key=lambda k: random.random()):
                # We add one to replicas because replicas are the COPIES we
                # write in addition to the base block.
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

        self.version.add_chunk(chunk)

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
        self.version.size = self._size
        self.version.md5 = self._md5.hexdigest()
        self.version.sha1 = self._sha1.hexdigest()
        # Flush to db.
        self.version.save(update_fields=['size', 'md5', 'sha1'])
        super().close()


class MulticloudFilesystem(MulticloudBase):
    def __init__(self, user, chunk_size=settings.CLOUDSTRYPE_CHUNK_SIZE,
                 replicas=0):
        super().__init__(user.get_clients())
        self.user = user
        self.chunk_size = chunk_size
        self.level = user.get_option('raid_level', 0)
        self.replicas = user.get_option('raid_replicas', replicas)

    def download(self, path, file=None, version=None):
        """
        Download from multiple storage.

        Uses Metastore backend to resolve path to a series of chunks. Returns a
        MulticloudReader that can read these chunks in order.
        """
        if file is None:
            try:
                file = UserFile.objects.get(path=path, user=self.user)
            except UserFile.DoesNotExist:
                raise FileNotFoundError(path)
        if version is None:
            version = file.file.version
        return MulticloudReader(self.user, self.storage, version)

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

        try:
            # Check user's hierarchy for the file.
            user_file = UserFile.objects.get(path=path, user=self.user)
            # If it exists, make a new version of it.
            version = user_file.file.add_version()
        except UserFile.DoesNotExist:
            # Attach that to a new file.
            file = File.objects.create(owner=self.user)
            # Place the new file into the user's hierarchy.
            user_file = UserFile.objects.create(
                path=path, file=file, name=basename(path), user=self.user)
            version = file.version

        # Upload the file.
        with MulticloudWriter(self.user, self.storage, version,
                              chunk_size=self.chunk_size,
                              replicas=self.replicas) as out:
            for chunk in chunker(f, chunk_size=self.chunk_size):
                out.write(chunk)
        return user_file

    @transaction.atomic
    def delete(self, path, file=None):
        """
        Delete from multiple storage.

        If path is a file it is deleted (as described below). If path is a
        directory then it is simply removed from the Metastore.

        Uses Metastore backend to resolve path to a series of chunks. Deletes
        the chunks from cloud providers and Metastore backend.
        """
        if file is None:
            try:
                file = UserFile.objects.get(path=path, user=self.user)
            except UserFile.DoesNotExist:
                raise FileNotFoundError(path)
        file.delete()

    @transaction.atomic
    def mkdir(self, path):
        if self.isfile(path):
            raise FileConflictError(path)
        return UserDir.objects.create(path=path, user=self.user)

    @transaction.atomic
    def rmdir(self, path, dir=None):
        if dir is None:
            try:
                dir = UserDir.objects.get(path=path, user=self.user)
            except UserDir.DoesNotExist:
                raise DirectoryNotFoundError(path)
        dir.delete()

    @transaction.atomic
    def _move_file(self, file, dst):
        if self.isdir(dst):
            raise DirectoryConflictError(dst)
        dst, file.name = pathsplit(dst.lstrip('/'))
        if dst:
            try:
                file.parent = \
                    UserDir.objects.get(path=dst, user=self.user)
            except UserDir.DoesNotExist:
                raise DirectoryNotFoundError(dst)
        file.save(update_fields=['parent', 'name'])
        return file

    @transaction.atomic
    def _move_dir(self, dir, dst):
        if self.isfile(dst):
            raise DirectoryConflictError(dst)
        # We need to relocate.
        try:
            dir.parent = \
                UserDir.objects.get(path=dst, user=self.user)
        except UserDir.DoesNotExist:
            if dirname(dst) == dirname(dir.path):
                # This is just a rename...
                dir.name = basename(dst)
                dir.save(update_fields=['name'])
                return dir
            raise DirectoryNotFoundError(dst)
        kwargs = {
            'user': self.user,
            'path': pathjoin(dst, dir.name),
        }
        UserDirQuerySet._args(UserDir, kwargs)
        for name, value in kwargs.items():
            setattr(dir, name, value)
        update_fields = ['parent']
        update_fields.extend(kwargs.keys())
        dir.save(update_fields=update_fields)
        return dir

    @transaction.atomic
    def move(self, src, dst):
        try:
            file = UserFile.objects.get(path=src, user=self.user)
            return self._move_file(file, dst)
        except UserFile.DoesNotExist:
            pass
        try:
            dir = UserDir.objects.get(path=src, user=self.user)
            return self._move_dir(dir, dst)
        except UserDir.DoesNotExist:
            pass
        raise PathNotFoundError(src)

    @transaction.atomic
    def _copy_file(self, srcfile, dst):
        if self.isdir(dst):
            dst = pathjoin(dst, srcfile.name)
        if self.isfile(dst):
            raise FileConflictError(dst)
        # Create a new file, attach the version from the original (copy).
        file = \
            File.objects.create(owner=self.user, version=srcfile.file.version)
        dstfile = \
            UserFile.objects.create(path=dst, file=file, user=self.user)
        return dstfile

    @transaction.atomic
    def _copy_dir(self, srcdir, dst):
        if self.isdir(dst):
            dst = pathjoin(dst, srcdir.name)
        if self.isfile(dst):
            raise FileConflictError(dst)
        # Clone dir first.
        dstdir = UserDir.objects.create(path=dst, user=self.user)
        # Then copy children recursively.
        for subdir in srcdir.child_dirs.all():
            self._copy_dir(subdir, dstdir.path)
        for subfile in srcdir.child_files.all():
            self._copy_file(subfile, dstdir.path)
        return dstdir

    @transaction.atomic
    def copy(self, src, dst):
        try:
            file = UserFile.objects.get(path=src, user=self.user)
            return self._copy_file(file, dst)
        except UserFile.DoesNotExist:
            pass
        try:
            dir = UserDir.objects.get(path=src, user=self.user)
            return self._copy_dir(dir, dst)
        except UserDir.DoesNotExist:
            pass
        raise PathNotFoundError('src')

    def listdir(self, path, dir=None):
        if dir is None:
            try:
                dir = UserDir.objects.get(path=path, user=self.user)
            except UserDir.DoesNotExist:
                raise DirectoryNotFoundError(path)
        dirs, files = dir.child_dirs.all(), dir.child_files.all()
        return DirectoryListing(dir, dirs, files)

    def info(self, path, file=None, dir=None):
        if file is not None:
            return file
        if dir is not None:
            return dir
        try:
            return UserFile.objects.get(path=path, user=self.user)
        except UserFile.DoesNotExist:
            pass
        try:
            return UserDir.objects.get(path=path, user=self.user)
        except UserDir.DoesNotExist:
            pass
        raise PathNotFoundError(path)

    def isdir(self, path):
        return UserDir.objects.filter(path=path, user=self.user).exists()

    def isfile(self, path):
        return UserFile.objects.filter(path=path, user=self.user).exists()

    def exists(self, path):
        return self.isdir(path) or self.isfile(path)
