import asyncio
import logging

from aiohttp import web

from django.core.management.base import BaseCommand


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


async def download(request):
    pass


async def upload(request):
    pass


class Command(BaseCommand):
    help = """FS Server.

    Provides an HTTP interface for filesystem operations."""

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8765,
                            help='Server port')
        parser.add_argument('--bind', default='localhost',
                            help='Server address to bind')

    def handle(self, *args, **kwargs):
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)

        loop = asyncio.get_event_loop()
        app = web.Application(loop=loop)

        app.router.add_get('/file/{id}/', download)
        app.router.add_put('/file/{id}/', upload)

        web.run_app(app, host='localhost', port=8080)
