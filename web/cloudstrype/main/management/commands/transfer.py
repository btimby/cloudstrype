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
from concurrent.futures import ThreadPoolExecutor
from collections import deque

from django.core.management.base import BaseCommand, CommandError


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

MAX_CONCURRENT_CHUNKS = 3


class ChunkReader(object):
    def _read_chunk(self, chunk):
        """Download a single chunk.

        May need to contact multiple providers to read a replica if the first
        provider fails."""
        for storage in chunk.storages.all():
            client = storage.get_client()
            try:
                return client.download(chunk)
            except:
                continue
        raise IOError('Could not read chunk')

    async def __iter__(self):
        """Read the chunks of a file.

        Uses futures and asyncio to parallelize the reading of chunks."""
        if self._closed:
            raise IOError('I/O operation on closed file')

        # We use the event loop to schedule futures. We only want a limited
        # number of futures executing at one time as chunks can be quite large.
        # Therefore we schedule several, and then await completion of the first
        # (oldest) and yield it before scheduling another (staying several
        # steps ahead).
        loop = asyncio.get_event_loop()
        q = deque(MAX_CONCURRENT_CHUNKS)
        exector = ThreadPoolExecutor()
        # TODO: implement getting chunks as future.
        chunks = <get_chunks_as_deque()>

        while True:
            # Start as many concurrent chunk downloads as we are allowed.
            while len(d) < MAX_CONCURRENT_CHUNKS and len(chunks):
                try:
                    d.append(loop.run_in_executor(executor, self._read_chunk,
                                                  chunks.popleft())
                except IndexError:
                    break

            # If futures are pending, wait for the oldest and yield it's result
            if len(d):
                task = await asyncio.wait_for(d.popleft())
                try:
                    yield task.result()
                except Exception as e:
                    # Cancel and return
                    while len(d):
                        d.popleft().cancel()
                    break

            # If there are no more pending futures, and no more chunks to get
            # we are done and can exit the loop.
            if not len(d) and not len(chunks):
                break


class ChunkWriter(object):
    def __init__(self):
        self.executor = ThreadPoolExecutor()

    def _write_chunk_replica(self, data, storage):
        """Write a chunk replica.

        Writes chunk data to a single provider."""
        cs = ChunkStorage(storage=storage)
        client = storage.get_client()
        cs.attrs = client.upload(data)
        return cs

    def _write_chunk(self, data):
        """Write a chunk.

        Handles writing multiple replicas in parallel."""
        chunk = Chunk()

        tasks = []
        goal = self.replicas
        # Try each up to three times.
        storages = itertools.chain(storages, storages, storages)

        while True:
            # Schedule enough replica writes to reach our goal.
            while goal:
                tasks.append(loop.run_in_executor(self.executor,
                                              self._write_chunk_replica, data,
                                              next(storages)))
                goal -= 1

            # Reap replica writes as they complete. Decrement goal for each
            # that succeeds.
            done, tasks = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED)

            for t in done:
                try:
                    cs.append(t.result())
                except:
                    goal += 1

        return chunk, cs

    @atomic
    def _write(self, f):
        """Transactional write.

        This future performs all database operations within a transaction."""
        loop = asyncio.get_event_loop()
        d = deque()

        for data in chunker(f):
            d.append(loop.run_in_executor(self.executor, self._write_chunk, data))

            # If we reach our limit for concurrent operations, block until one
            # completes.
            if len(d) == MAX_CONCURRENT_CHUNKS:
                chunk, chunkstorages = await asyncio.wait_for(d.popleft())
                chunk.save()
                for cs in chunkstorages:
                    cs.chunk = chunk
                    cs.save()

    async def write(self, f):
        """Write multiple replicas of each chunk of a file.

        Uses a future to write a file chunk by chunk."""
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(self.executor, self._write, f)
        await asyncio.wait_for(task)



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
