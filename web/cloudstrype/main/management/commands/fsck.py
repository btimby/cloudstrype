import logging

from hashlib import md5, sha1

from django.core.management.base import BaseCommand

from main.fs import crc32, get_fs
from main.models import User, File


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


class Command(BaseCommand):
    help = """File System ChecK.

    Checks integrity of file system."""

    def add_arguments(self, parser):
        parser.add_argument('--quick', action='store_true',
                            help='Perform quick file check')
        parser.add_argument('--versions', action='store_true',
                            help='Check all file versions')
        pass

    def handle_chunk(self, fs, chunk):
        data = None
        for s in chunk.storages.all():
            cloud = s.storage.get_client()
            try:
                maybe_data = cloud.download(chunk)
                if len(maybe_data) != chunk.size:
                    LOGGER.warning('%s:%s Size mismatch', chunk.uid, s)
                if crc32(maybe_data) != chunk.crc32:
                    LOGGER.warning('%s:%s CRC32 mismatch', chunk.uid, s)
                if md5(maybe_data).hexdigest() != chunk.md5:
                    LOGGER.warning('%s:%s MD5 mismatch', chunk.uid, s)
                # Here is where I would otherwise return good data, but we want
                # to keep checking so I will store it in data, which we return
                # later.
                data = maybe_data
            except Exception as e:
                LOGGER.warning('%s:%s Download error', chunk.uid, s)
                LOGGER.exception(e)
                continue
        return data

    def handle_file(self, fs, file):
        if self.versions:
            # Check all versions.
            versions = file.versions.all()
        else:
            # Check current version
            versions = [file.version]

        if self.quick:
            # Just read one replica per chunk (a random one). The reader checks
            # integrity using assertions.
            for version in versions:
                hash_md5, hash_sha1 = md5(), sha1()
                download = fs.download(file)
                while True:
                    try:
                        d = next(download)
                        hash_md5.update(d)
                        hash_sha1.update(d)
                    except StopIteration:
                        break
                    except AssertionError as e:
                        LOGGER.warning('%s Bad chunk', file.uid)
                if hash_md5.hexdigest() == file.version.md5:
                    LOGGER.warning('File %s Invalid md5', file.uid)
                if hash_sha1.hexdigest() == file.version.sha1:
                    LOGGER.warning('File %s Invalid sha1', file.uid)
            return

        # Do a slower, more complete check of every replica of every chunk.
        for version in versions:
            hash_md5, hash_sha1 = md5(), sha1()
            for c in version.chunks.all():
                # Check each Chunk.
                d = self.handle_chunk(fs, c)
                hash_md5.update(d)
                hash_sha1.update(d)

            if hash_md5.hexdigest() == file.version.md5:
                LOGGER.warning('File %s Invalid md5', file.uid)
            if hash_sha1.hexdigest() == file.version.sha1:
                LOGGER.warning('File %s Invalid sha1', file.uid)

    def handle_user(self, user):
        fs = get_fs(user)
        for f in File.objects.filter(owner=user):
            # Every one of their files (excluding dead files).
            try:
                self.handle_file(fs, f)
            except Exception as e:
                LOGGER.warning('%s:%s Error handling file', user.uid, f.uid)
                LOGGER.exception(e)

    def handle(self, *args, **kwargs):
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)

        self.quick = kwargs['quick']
        self.versions = kwargs['versions']

        # Naive implementation.
        for u in User.objects.all():
            # Every user is checked.
            self.handle_user(u)
