"""
Provide high-level GET/PUT operations for files.

Handles low-level communication with cloud providers, transistions between
chunks and whole files.

This server interacts with the application server and the front-end load
balancer (nginx).

Upload flow:
 1. Upload from client is handled by nginx (written to /tmp).
 2. Upload handed off to uWSGI application, which auths users and performs
    validation.
 3. Upload handed off to aiohttp server, temp file path passed.
 4. Application waits for aiohttp and nginx waits for application.

 * https://www.nginx.com/resources/wiki/modules/upload/

 5. Optionally, once upload access is verified by the application, it can return
    a response to nginx causing it to communicate with aiohttp directly. The
    upload could proceed and the final response returned by aiohttp. In this
    way the application server would not have to wait for the cloud upload to
    complete.

 * https://www.nginx.com/resources/wiki/start/topics/examples/x-accel/#x-accel-redirect

 [User]->[Nginx]<->[uWSGI]<->[AIOHTTP]->[clouds]
            ^                   ^
            |                   |
            +------>[tmp]-------+

 - OR -

 [User]->[Nginx]<-(redirect)->[uWSGI]
            ^
            |
            v
          [tmp]<->[AIOHTTP]->[clouds]

 Download flow:
 1. Download request hits application via nginx.
 2. Perform validation and auth.
 3. Redirect nginx to aiohttp, which will stream chunks via nginx to caller.

 * https://kovyrin.net/2010/07/24/nginx-fu-x-accel-redirect-remote/

 [User]<->[Nginx]<-(redirect)->[uWSGI]
             ^
             |
             v
         [AIOHTTP]<--[clouds]

https://hub.docker.com/r/dimka2014/nginx-upload-with-progress-modules/
"""

import asyncio
import logging

from aiohttp import web

from django.core.management.base import BaseCommand, CommandError


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


async def download(request):
    """
    Download a file from clouds.

    Incrementally downloads a file from cloud providers. Starts downloading up
    to 5 chunks at once and as each is returned (in order) another chunk is
    started. Handles retries.

    Can be passed a specific verison, otherwise, it locates the most recent
    version and returns that.
    """
    # The request should include the file name in path. This is for naming the
    # file and will be echoed in the Content-Disposition header. The query
    # string should consist of the uid of the file we wish to transfer. The
    # transfer is done using chunked encoding, each chunk is returned as,
    # well... a chunk.
    name, uid = request.path, request.query_string
    


async def upload(request):
    """
    Upload a file to clouds.

    Accepts a file body or temp file path. Chunks the file, replicates it and
    uploads to multiple cloud providers.
    """
    pass


async def handler(request):
    """
    Handle web request.

    Validate and then dispatch to upload()/download().
    """
    if request.method == 'GET':
        return await download(request)
    elif request.method in ('PUT', 'POST'):
        return await upload(request)
    else:
        return web.Response(status=409, text='Method not allowed')


class Command(BaseCommand):
    help = """Transfer to/from cloud."""

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8001,
                            help='HTTP server port')
        parser.add_argument('--bind', default='localhost',
                            help='Server address to bind')

    def handle(self, *args, bind='localhost', port=8001, **kwargs):
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)

        loop = asyncio.get_event_loop()

        # Create low-level aiohttp server.
        server = web.Server(handler)
        loop.run_until_complete(loop.create_server(bind, port))

        loop.run_forever()
