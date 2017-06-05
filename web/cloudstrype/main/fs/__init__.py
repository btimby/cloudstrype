"""
I would like to remove this to a dedicated async HTTP server.

Upload flow:
 1 Upload handled by nginx (written to /tmp).
 2 Upload handed off to uWSGI application, which auths users and performs
   validation.
 3 Upload handed off to aiohttp server, temp file path passed.
 4 Application waits for aiohttp and nginx waits for application. BUT perhaps
   X-Accel-Redirect can be used even for this upload... Then uWSGI can get out
   of the way.
 - https://www.nginx.com/resources/wiki/modules/upload/

 [User] -> [Nginx] -> [uWSGI] -> [AIOHTTP]
              |                      ^
              |                      |
              +--------[disk]--------+

 Download flow:
 1 Download request hits application via nginx.
 2 Perform validation and auth.
 3 Redirect nginx to aiohttp, which will stream chunks via nginx to caller.
 - https://kovyrin.net/2010/07/24/nginx-fu-x-accel-redirect-remote/

 [User] <- [Nginx] <-> [uWSGI]
              ^
              |
              v
           [AIOHTTP]
"""

import collections
import random
import logging
import mimetypes

from os.path import join as pathjoin
from os.path import split as pathsplit
from os.path import (
    dirname, basename
)
from hashlib import md5, sha1

import magic

from django.conf import settings
from django.core.cache import caches
from django.db import transaction

from main.models import (
    UserDir, UserFile, File, FileTag, Chunk, ChunkStorage,
)
from main.fs.raid import chunker
from main.fs.errors import (
    DirectoryNotFoundError, FileNotFoundError, PathNotFoundError,
    DirectoryConflictError, FileConflictError
)


REPLICAS = 2
LOGGER = logging.getLogger(__name__)
CHUNK_CACHE = caches['chunks']


DirectoryListing = collections.namedtuple('DirectoryListing',
                                          ('dir', 'dirs', 'files'))


class MultiCloudBase(object):
    """
    Base class for interacting with multiple clouds.
    """

    def __init__(self, user):
        self.user = user
        self.storage = user.storages.all()


class FileLikeBase(object):
    """
    Implement File-like methods.

    Implements methods shared by both MultiCloudReader and MultiCloudWriter.
    """

    def __enter__(self):
        return self

    def __exit__(self, type, value, tb):
        self.close()

    def tell(self):
        # This should be fairly easy to implement. For MultiCloudWriter, we
        # have size, and could keep count on MultiCloudReader to provided this.
        raise NotImplementedError()

    def seek(self):
        # TODO: This could possibly be implemented, and could be useful for
        # range requests.
        raise NotImplementedError()

    def flush(self):
        # N/A
        pass

    def close(self):
        # No resources to release, so mark as closed.
        if self._closed:
            raise IOError('Already closed.')
        self._closed = True


class MultiCloudReader(MultiCloudBase, FileLikeBase):
    """
    File-like object that reads from multiple clouds.
    """
    def __init__(self, user, version):
        super().__init__(user)
        self.version = version
        self.chunks = list(
            Chunk.objects.filter(
                filechunks__version=version).order_by('filechunks__serial')
        )
        self._buffer = []
        self._closed = False

    def _read_chunk(self):
        try:
            chunk = self.chunks.pop(0)
        except IndexError:
            raise EOFError('out of chunks')
        data = CHUNK_CACHE.get('chunk:%s' % chunk.uid)
        if data is not None:
            return chunk.unpack(data)
        # Try providers in random order.
        for cs in sorted(chunk.storages.all(), key=lambda k: random.random()):
            # Since chunks are shared with other users, we need to get the
            # client for the chunk, not one of the clients for the current
            # user.
            client = cs.storage.get_client()
            try:
                data = client.download(chunk)
            except Exception as e:
                LOGGER.exception(e)
                continue
            unpacked = chunk.unpack(data)
            CHUNK_CACHE.set('chunk:%s' % chunk.uid, data)
            return unpacked
        raise IOError('Failed to read chunk %s' % chunk.uid)

    def __iter__(self):
        if self._closed:
            raise IOError('I/O operation on closed file.')
        while self.chunks:
            yield self.read()

    def read(self, size=-1):  # NOQA
        """
        Read series of chunks from multiple clouds.
        """
        if self._closed:
            raise IOError('I/O operation on closed file.')
        try:
            return self._read_chunk()
        except EOFError:
            return


class MultiCloudWriter(MultiCloudBase, FileLikeBase):
    """
    File-like object that writes to multiple clouds.
    """
    def __init__(self, user, file, version,
                 chunk_size=settings.CLOUDSTRYPE_CHUNK_SIZE,
                 replicas=REPLICAS):
        super().__init__(user)
        self.mime = mimetypes.guess_type(file.name, strict=False)
        self.version = version
        self.chunk_size = chunk_size
        self.replicas = replicas
        self._md5 = md5()
        self._sha1 = sha1()
        self._size = 0
        self._buffer = []
        self._closed = False

    def _write_chunk(self, data):
        """
        Write a single chunk.

        Writes chunk to multiple clouds.
        """
        chunk = Chunk.objects.create(size=len(data), user=self.user)
        data = chunk.pack(data)

        # Upload to N random providers where N is desired replica count.
        chunks_uploaded = 0
        for storage in sorted(self.storage, key=lambda k: random.random()):
            # We add one to replicas because replicas are the COPIES we
            # write in addition to the base block.
            if chunks_uploaded == self.replicas + 1:
                break
            client = storage.get_client()
            try:
                attrs = client.upload(chunk, data)
            except Exception as e:
                LOGGER.exception(e)
                continue
            cs = ChunkStorage(chunk=chunk, storage=storage)
            cs.attrs = attrs or {}
            cs.save()
            chunk.storages.add(cs)
            chunks_uploaded += 1
        if chunks_uploaded < self.replicas + 1:
            raise IOError('Failed to write chunk')

        # Freshen the cache.
        CHUNK_CACHE.set('chunk:%s' % chunk.uid, data)
        self.version.add_chunk(chunk)

    def write(self, data):
        """
        Write data to multiple clouds.

        Uses a write-through buffer to ensure each chunk is the proper size.
        Close flushes the remainder of the buffer.
        """
        if self._closed:
            raise IOError('I/O operation on closed file.')
        if self._size == 0:
            # First block. See if we can get a more specific mime type by
            # examining the data.
            mime = magic.from_buffer(data, mime=True)
            # Choose the better mimetype somehow, self.mime is determined by
            # the filename. mime is determined by magic.
            if not self.mime or mime != 'application/octet-strem':
                self.mime = mime
        self._size += len(data)
        self._md5.update(data)
        self._sha1.update(data)
        self._write_chunk(data)

    def close(self):
        """
        Finalize file by writing attributes.
        """
        super().close()
        # Update content related attributes.
        self.version.size = self._size
        self.version.md5 = self._md5.hexdigest()
        self.version.sha1 = self._sha1.hexdigest()
        # Flush to db.
        self.version.save(update_fields=['size', 'md5', 'sha1'])


class MultiCloudFilesystem(MultiCloudBase):
    def __init__(self, user, chunk_size=settings.CLOUDSTRYPE_CHUNK_SIZE,
                 replicas=0):
        super().__init__(user)
        self.chunk_size = chunk_size
        self.level = user.get_option('raid_level', 0)
        self.replicas = user.get_option('raid_replicas', replicas)

    def download(self, path, file=None, version=None):
        """
        Download from multiple storage.

        Uses Metastore backend to resolve path to a series of chunks. Returns a
        MultiCloudReader that can read these chunks in order.
        """
        # If caller did not give a file (only a path), lookup the file by path.
        if file is None:
            try:
                file = UserFile.objects.get(path=path, user=self.user)
            except UserFile.DoesNotExist:
                raise FileNotFoundError(path)
        # If caller did not specify version, select the current one.
        if version is None:
            version = file.file.version
        return MultiCloudReader(self.user, version)

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
            # Place the new file into the user's hierarchy.
            user_file = UserFile.objects.create(
                path=path, name=basename(path), user=self.user)
            # Grab ref to version, since we upload to THAT.
            version = user_file.file.version

        # Upload the file.
        size, count = 0, 0
        with MultiCloudWriter(self.user, user_file, version,
                              chunk_size=self.chunk_size,
                              replicas=self.replicas) as out:
            for data in chunker(f, chunk_size=self.chunk_size):
                size += len(data)
                count += 1
                out.write(data)

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

    def mkdir(self, path):
        if self.isfile(path):
            raise FileConflictError(path)
        return UserDir.objects.create(path=path, user=self.user)

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
        try:
            # First try moving the directory to the given path. If this fails,
            # it means the given path does not exist, and thus the given path
            # is the intended name of dir.
            dir.parent = \
                UserDir.objects.get(path=dst, user=self.user)
        except UserDir.DoesNotExist:
            # If the given path does not exist (not intended to be parent)
            # maybe we just need to rename.
            if dirname(dst) == dirname(dir.path):
                # This is just a rename...
                dir.name = basename(dst)
                dir.save(update_fields=['name'])
                return dir
            # No, in this case, we were asked to move to a non-existant
            # directory so raise.
            raise DirectoryNotFoundError(dst)
        else:
            # OK, the parent has been changed, we move it into the requested
            # directory.
            dir.save(update_fields=['parent'])
        return dir

    def move(self, src, dst):
        # Is it a file?
        try:
            file = UserFile.objects.get(path=src, user=self.user)
            # Move it.
            return self._move_file(file, dst)
        except UserFile.DoesNotExist:
            pass
        # No, is it a dir?
        try:
            dir = UserDir.objects.get(path=src, user=self.user)
            # Move it.
            return self._move_dir(dir, dst)
        except UserDir.DoesNotExist:
            pass
        # Neither, raise.
        raise PathNotFoundError(src)

    @transaction.atomic
    def _copy_file(self, srcfile, dst):
        # If destination is a directory, then put this file inside of it.
        if self.isdir(dst):
            dst = pathjoin(dst, srcfile.name)
        # If destination exists, raise conflict. Remember, this is not an elif,
        # so we are checking the original destination if it was not a directory
        # or the adjusted one if it was a directory.
        if self.exists(dst):
            raise FileConflictError(dst)
        # Create a new file, attach the version from the original (copy).
        file = \
            File.objects.create(owner=self.user, version=srcfile.file.version)
        # Place the new file into the user's hierarchy.
        dstfile = UserFile.objects.create(path=dst, file=file, user=self.user,
                                          attrs=srcfile.attrs)
        for tag in srcfile.tags.all():
            FileTag.objects.create(file=dstfile, tag=tag)
        return dstfile

    @transaction.atomic
    def _copy_dir(self, srcdir, dst):
        # If destination is a directory, then put this directory inside of it.
        if self.isdir(dst):
            dst = pathjoin(dst, srcdir.name)
        # If destination exists, raise conflict. Remember, this is not an elif,
        # so we are checking the original destination if it was not a directory
        # or the adjusted one if it was a directory.
        if self.exists(dst):
            raise FileConflictError(dst)
        # Clone srcdir first.
        dstdir = UserDir.objects.create(path=dst, user=self.user,
                                        attrs=srcdir.attrs)
        for tag in srcdir.tags.all():
            dstdir.tags.add(tag)
        # Then copy children recursively.
        for subdir in srcdir.child_dirs.all():
            self._copy_dir(subdir, dstdir.path)
        for subfile in srcdir.child_files.all():
            self._copy_file(subfile, dstdir.path)
        return dstdir

    def copy(self, src, dst):
        # Is it a file?
        try:
            file = UserFile.objects.get(path=src, user=self.user)
            # Copy it.
            return self._copy_file(file, dst)
        except UserFile.DoesNotExist:
            pass
        # No, is it a dir?
        try:
            dir = UserDir.objects.get(path=src, user=self.user)
            # Copy it.
            return self._copy_dir(dir, dst)
        except UserDir.DoesNotExist:
            pass
        # Neither, raise.
        raise PathNotFoundError('src')

    def listdir(self, path, dir=None):
        if dir is None:
            try:
                dir = UserDir.objects.get(path=path, user=self.user)
            except UserDir.DoesNotExist:
                raise DirectoryNotFoundError(path)
        return DirectoryListing(
            dir,
            dir.child_dirs.all(),
            dir.child_files.all()
        )

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
        return self.isdir(path) or \
               self.isfile(path)


def get_fs(user, **kwargs):
    return MultiCloudFilesystem(user, **kwargs)
