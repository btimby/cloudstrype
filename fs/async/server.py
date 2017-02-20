import json
import logging

import asyncio
import aiohttp

from aiohttp import web

from cloud.dropbox import DropboxProvider

LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler())

DROPBOX_TOKEN = ''

FILES = [
    '/seeds/f20.jpg',
    '/seeds/f25.jpg',
    '/seeds/f26.jpg',
]


class SplitStream(object):
    """
    Read a stream in chunks.
    """
    def __init__(self, input):
        self.input = input

    def read(self, size=-1):
        while True:
            chunk = self.input.read(size)
            if not chunk:
                break
            yield chunk


class JoinedStream(object):
    """
    Join chunks into a stream.
    """
    def __init__(self, chunks):
        self.chunks = chunks

    def read(self, size=-1):
        for chunk in chunks:
            yield chunk.read()


async def download(request):
    provider = DropboxProvider({'token': DROPBOX_TOKEN})
    server = await provider.read(FILES[0])

    response = web.StreamResponse()
    response.content_type = 'image/jpg'

    await response.prepare(request)
    body = await server.read()
    response.write(body)
    response.write_eof()
    return response


@asyncio.coroutine
def upload(request):
    pass


def main():
    app = web.Application()
    app.router.add_get('', download)
    app.router.add_post('', upload)

    event_loop = asyncio.get_event_loop()

    factory = event_loop.create_server(app.make_handler(), '0.0.0.0', 8080)
    event_loop.run_until_complete(factory)

    try:
        event_loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        factory.close()
        event_loop.close()


if __name__ == '__main__':
    main()
