from hashlib import md5

from django.core.management.base import BaseCommand, CommandError

from main.fs.raid import DEFAULT_CHUNK_SIZE
from main.models import OAuth2StorageToken, Chunk, ChunkStorage


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
            token = OAuth2StorageToken.objects.get(pk=kwargs['cloud'])
        except OAuth2StorageToken.DoesNotExist:
            raise CommandError('Invalid cloud uid %s' % kwargs['cloud'])
        client = token.get_client()

        if kwargs['upload']:
            with open('/dev/random', 'rb') as r:
                data = r.read(DEFAULT_CHUNK_SIZE)
            chunk = Chunk.objects.create(md5=md5(data).hexdigest())
            chunk.storage.add(
                ChunkStorage.objects.create(chunk=chunk,
                                            storage=client.oauth_storage))
            client.upload(chunk, data)
            print('Chunk uploaded. id=%s, size=%s' % (chunk.id, len(data)))

        if kwargs['download']:
            try:
                chunk = Chunk.objects.get(id=kwargs['download'])
            except Chunk.DoesNotExist:
                raise CommandError('Invalid chunk id %s' % kwargs['download'])
            data = client.download(chunk)
            print('Chunk downloaded. size=%s' % len(data))
            assert md5(data).hexdigest() == chunk.md5, \
                'Chunk verification failed'
            print('Chunk verified.')
