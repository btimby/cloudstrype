from hashlib import md5

from django.core.management.base import BaseCommand, CommandError

from main.fs import crc32
from main.fs.raid import DEFAULT_CHUNK_SIZE
from main.models import OAuth2UserStorage, Chunk, ChunkStorage


class Command(BaseCommand):
    help = """Upload/download chunk to/from cloud.

    Uploading prints the chunk id, which you can pass to download to download
    that chunk."""

    def add_arguments(self, parser):
        parser.add_argument('transfer', type=int)
        parser.add_argument('--download',
                            help='Perform download, must provide chunk uid')
        parser.add_argument('--upload', action='store_true',
                            help='Perform upload, generates random chunk.')

    def handle(self, *args, **kwargs):
        try:
            token = OAuth2UserStorage.objects.get(pk=kwargs['transfer'])
        except OAuth2UserStorage.DoesNotExist:
            raise CommandError('Invalid cloud uid %s' % kwargs['transfer'])

        client = token.get_client()

        if kwargs['upload']:
            with open('/dev/random', 'rb') as r:
                data = r.read(DEFAULT_CHUNK_SIZE)

            chunk = Chunk.objects.create(
                md5=md5(data).hexdigest(), size=len(data), crc32=crc32(data))
            chunk.storage.add(
                ChunkStorage.objects.create(chunk=chunk,
                                            storage=client.user_storage))

            client.upload(chunk, data)

            print('Chunk uploaded. id=%s, size=%s, crc32=%s, md5=%s' %
                  (chunk.id, chunk.size, chunk.crc32, chunk.md5))

        if kwargs['download']:
            try:
                chunk = Chunk.objects.get(id=kwargs['download'])
            except Chunk.DoesNotExist:
                raise CommandError('Invalid chunk id %s' % kwargs['download'])

            data = client.download(chunk)

            print('Chunk downloaded. id=%s, size=%s, crc32=%s, md5=%s' %
                  (chunk.id, chunk.size, chunk.crc32, chunk.md5))

            assert len(data) == chunk.size, \
                'Chunk verification failed'
            assert crc32(data) == chunk.crc32, \
                'Chunk verification failed'
            assert md5(data).hexdigest() == chunk.md5, \
                'Chunk verification failed'

            print('Chunk verified.')
