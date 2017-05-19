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
from zlib import crc32 as _crc32

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


def twos_complement(input_value, num_bits):
    """Calculate two's complement integer from the given input value's bits."""
    mask = 2 ** (num_bits - 1)
    return -(input_value & mask) + (input_value & ~mask)


def crc32(data):
    return twos_complement(_crc32(data), 32)


DirectoryListing = collections.namedtuple('DirectoryListing',
                                          ('dir', 'dirs', 'files'))


class FileInfo(object):
    isfile = True
    isdir = False

    def __init__(self, obj, user=None):
        self.object = obj
        if obj.user != user:
            if user is None:
                user = obj.user

        # Copy attributes from the File/Directory instance for the user that is
        # going to view them.
        self.user = user
        self.name = obj.get_name(user)
        self.path = obj.get_path(user)
        try:
            self.extension = obj.get_extension(user)
        except AttributeError:
            pass

    def __getattr__(self, name):
        try:
            return self.__getattribute__(name)
        except AttributeError:
            return getattr(self.object, name)


class DirInfo(FileInfo):
    isfile = False
    isdir = True


class RootInfo(DirInfo):
    """
    Fake info for the / path.
    """
    def __init__(self, user):
        self.user = user
        self.parent = None
        self.name = '/'
        self.created = None
        self.tags = []
        self.attrs = {}


class InfoView(object):
    def __init__(self, objects, user, Info):
        self.objects = objects
        self.user = user
        self.Info = Info

    def __iter__(self):
        for o in self.objects:
            yield self.Info(o, self.user)

    def __len__(self):
        return len(self.objects)


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
                filechunks__fileversion=version).order_by('filechunks__serial')
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

    def download(self, path, file=None):
        """
        Download from multiple storage.

        Uses Metastore backend to resolve path to a series of chunks. Returns a
        MulticloudReader that can read these chunks in order.
        """
        if file is None:
            try:
                file = File.objects.get(path=path, user=self.user)
            except File.DoesNotExist:
                raise FileNotFoundError(path)
        return MulticloudReader(self.user, self.storage, file.version)

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

        file, _ = File.objects.get_or_create(path=path, user=self.user)
        version = file.add_version()

        with MulticloudWriter(self.user, self.storage, version,
                              chunk_size=self.chunk_size,
                              replicas=self.replicas) as out:
            for chunk in chunker(f, chunk_size=self.chunk_size):
                out.write(chunk)
        return FileInfo(file, self.user)

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
                file = File.objects.get(path=path, user=self.user)
            except File.DoesNotExist:
                raise FileNotFoundError(path)
        # We do not care about order...
        for chunk in Chunk.objects.filter(filechunks__fileversion=file.version):
            for storage in chunk.storage.all():
                cloud = self.get_storage(storage.storage)
                try:
                    cloud.delete(chunk)
                except Exception as e:
                    LOGGER.exception(e)
                    continue
        file.delete()

    @transaction.atomic
    def mkdir(self, path):
        if self.isfile(path):
            raise FileConflictError(path)
        return DirInfo(
            Directory.objects.create(path=path, user=self.user), self.user)

    @transaction.atomic
    def rmdir(self, path, dir=None):
        if dir is None:
            try:
                dir = Directory.objects.get(path=path, user=self.user)
            except Directory.DoesNotExist:
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
        DirectoryQuerySet._args(Directory, kwargs)
        for name, value in kwargs.items():
            setattr(dir, name, value)
        dir.save()
        return dir

    @transaction.atomic
    def move(self, src, dst):
        try:
            file = File.objects.get(path=src, user=self.user)
            return FileInfo(self._move_file(file, dst), self.user)
        except File.DoesNotExist:
            pass
        try:
            dir = Directory.objects.get(path=src, user=self.user)
            return DirInfo(self._move_dir(dir, dst), self.user)
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
            File.objects.create(size=srcfile.size, md5=srcfile.md5,
                                sha1=srcfile.sha1, mime=srcfile.mime, path=dst,
                                user=self.user)
        # Then clone it's chunks:
        for chunk in Chunk.objects.filter(filechunks__fileversion=srcfile.version).order_by(
                                          'filechunks__serial'):
            dstfile.version.add_chunk(chunk)
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
        _, dirs, files = self.listdir(srcdir.get_path(self.user), dir=srcdir)
        for subdir in dirs:
            self._copy_dir(subdir, dstdir.get_path(self.user))
        for subfile in files:
            self._copy_file(subfile, dstdir.get_path(self.user))
        return dstdir

    @transaction.atomic
    def copy(self, src, dst):
        try:
            file = File.objects.get(path=src, user=self.user)
            return FileInfo(self._copy_file(file, dst), self.user)
        except File.DoesNotExist:
            pass
        try:
            dir = Directory.objects.get(path=src, user=self.user)
            return DirInfo(self._copy_dir(dir, dst), self.user)
        except Directory.DoesNotExist:
            pass
        raise PathNotFoundError('src')

    def listdir(self, path, dir=None):
        if path == '/':
            dir = None
        elif dir is None:
            try:
                dir = Directory.objects.get(path=path, user=self.user)
            except Directory.DoesNotExist:
                raise DirectoryNotFoundError(path)
        dirs, files = Directory.objects.children_of(dir, self.user)
        dir = DirInfo(dir, self.user) if dir else RootInfo(self.user)
        return DirectoryListing(
            dir,
            InfoView(dirs, self.user, DirInfo),
            InfoView(files, self.user, FileInfo)
        )

    def info(self, path, file=None, dir=None):
        if path == '/':
            return RootInfo(self.user)
        if file is not None:
            return FileInfo(file, self.user)
        if dir is not None:
            return DirInfo(dir, self.user)
        dir, name = pathsplit(path.lstrip('/'))
        dir = dir if dir else None
        if dir:
            try:
                dir = Directory.objects.get(path=dir, user=self.user)
            except Directory.DoesNotExist:
                raise PathNotFoundError(path)
        dirs, files = Directory.objects.children_of(dir, self.user, name=name)
        if dirs.first():
            return DirInfo(dirs.first(), self.user)
        if files.first():
            return FileInfo(files.first(), self.user)
        raise PathNotFoundError(path)

    def isdir(self, path):
        try:
            return self.info(path).isdir
        except PathNotFoundError:
            return False

    def isfile(self, path):
        try:
            return self.info(path).isfile
        except PathNotFoundError:
            return False

    def exists(self, path):
        if path == '/':
            return True
        return self.isdir(path) or self.isfile(path)
