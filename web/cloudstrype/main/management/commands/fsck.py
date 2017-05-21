import logging

from hashlib import md5, sha1

from django.core.management.base import BaseCommand

from main.fs import crc32, get_fs
from main.models import User, UserFileView


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
        for s in chunk.storage.all():
            cloud = fs.get_storage(s.storage)
            try:
                maybe_data = cloud.download(chunk)
                if len(data) != chunk.size:
                    LOGGER.warning('%s:%s Size mismatch', chunk.uid, s.uid)
                if crc32(data) != chunk.crc32:
                    LOGGER.warning('%s:%s CRC32 mismatch', chunk.uid, s.uid)
                # Here is where I would otherwise return good data, but we want
                # to keep checking so I will store it in data, which we return
                # later.
                data = maybe_data
            except Exception as e:
                LOGGER.warning('%s:%s Download error', chunk.uid, s.uid)
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
                while True:
                    try:
                        next(fs.download(file))
                    except StopIteration:
                        break
                    except AssertionError as e:
                        LOGGER.warning('%s:%s Bad chunk', file.user.uid,
                                       file.uid)
            return

        # Do a slower, more complete check of every replica of every chunk.
        for version in versions:
            hash_md5, hash_sha1 = md5(), sha1()
            for c in version.chunks.all():
                # Check each Chunk.
                d = self.handle_chunk(c)
                hash_md5.update(d)
                hash_sha1.update(d)

            if hash_md5.hexdigest() == file.version.md5:
                LOGGER.warning('%s:%s Invalid md5', file.user.uid, file.uid)
            if hash_sha1.hexdigest() == file.version.sha1:
                LOGGER.warning('%s:%s Invalid sha1', file.user.uid, file.uid)

    def handle_user(self, user):
        fs = get_fs(user)
        for f in UserFileView.objects.filter(user=user):
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
        self.version = kwargs['versions']

        # Naive implementation.
        for u in User.objects.all():
            # Every user is checked.
            self.handle_user(u)
