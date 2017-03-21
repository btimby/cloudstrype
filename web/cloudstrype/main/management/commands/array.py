import uuid
import struct
import asyncio
import logging

import websockets

from urllib.parse import parse_qs

from django.core.management.base import BaseCommand


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


HTTP_STATUS = {
    200: b'OK',
    404: b'NOT FOUND',
    503: b'UNAVAILABLE',
}
HTML_ERROR = b'<html><body>%b</body></html>'


async def start_response(writer, content_type='text/html', status=200,
                         headers={}):
    writer.write(b'HTTP/1.1 %b %b\r\n' %
                 (bytes(str(status), 'ascii'), HTTP_STATUS.get(status, 'NA')))
    writer.write(b'Content-Type: %b\r\n' % bytes(content_type, 'ascii'))
    for name, value in headers.items():
        if isinstance(value, int):
            value = str(value)
        if isinstance(value, str):
            value = bytes(value, 'ascii')
        writer.write(b'%b: %b\r\n' % (bytes(name, 'ascii'), value))
    writer.write(b'\r\n')
    await writer.drain()


async def error_response(writer, status, message):
    body = HTML_ERROR % message
    await start_response(
        writer, status=status, headers={'Content-Length': len(body)})
    writer.write(body)
    await writer.drain()
    writer.close()


class ArrayCommand(object):
    COMMAND_GET = 0
    COMMAND_PUT = 1
    COMMAND_DELETE = 2

    COMMAND_NAMES = {
        COMMAND_GET: 'GET',
        COMMAND_PUT: 'PUT',
        COMMAND_DELETE: 'DELETE',
    }

    COMMAND_TYPES = {v: n for n, v in COMMAND_NAMES.items()}

    STATUS_NONE = 0
    STATUS_SUCCESS = 1
    STATUS_ERROR = 2

    STATUS_NAMES = {
        STATUS_NONE: 'NONE',
        STATUS_SUCCESS: 'SUCCESS',
        STATUS_ERROR: 'ERROR',
    }

    STATUS_TYPES = {v: n for n, v in STATUS_NAMES.items()}

    FORMAT = '<bb24si'

    def __init__(self, type, status=STATUS_NONE, id=b''):
        if isinstance(type, str):
            # Convert HTTP method string to integer.
            type = self.COMMAND_TYPES[type]
        assert type in (self.COMMAND_GET, self.COMMAND_PUT,
                        self.COMMAND_DELETE)
        assert type in (self.STATUS_NONE, self.STATUS_SUCCESS,
                        self.STATUS_ERROR)
        self.type = type
        self.status = status
        self.id = id
        self.length = 0
        self.data = b''

    def __bytes__(self):
        assert len(self.data) == self.length
        assert len(self.id) == 24
        return struct.pack(self.FORMAT, self.type, self.status, self.id,
                           self.length) + self.data

    @staticmethod
    def decode(buffer):
        cmd = ArrayCommand(buffer[0], buffer[1], id=buffer[2:26])
        cmd.length = struct.unpack('<i', buffer[26:30])[0]
        cmd.data = buffer[30:]
        assert len(cmd.data) == cmd.length
        assert len(cmd.id) == 24
        return cmd

    @property
    def name(self):
        return self.COMMAND_NAMES[self.type]

    @property
    def status_name(self):
        return self.STATUS_NAMES[self.status]


class ArrayServer(object):
    # TODO: combine with Client class. We can detect the path and "upgrade" to
    # a websocket for certain clients, or handle as HTTP for others.
    def __init__(self, client):
        self.client = client

    async def handle(self, reader, writer):
        request = await reader.readline()
        if request == b'':
            LOGGER.debug("Empty request")
            await writer.aclose()
            return

        method, path, http = request.decode().split()
        assert method in ('GET', 'PUT', 'DELETE')
        assert http == 'HTTP/1.1'

        try:
            path, querystring = path.split('?', 1)
        except ValueError as e:
            querystring = {}
        else:
            querystring = parse_qs(querystring)

        # path == <client GUID>/<chunk ID>
        try:
            client_id, chunk_id = path.strip('/').split('/', 1)
        except ValueError as e:
            LOGGER.debug(e)
            await error_response(writer, 404, b'Not Found')
            return

        try:
            client_id = uuid.UUID(client_id)
        except ValueError as e:
            LOGGER.debug(e)
            await error_response(writer, 404, b'Not Found')
            return

        if client_id not in self.client.clients:
            LOGGER.debug('"%s" not in (%s)' % (client_id, self.client.clients))
            await error_response(writer, 404, b'Not Found')
            return

        # Parse headers.
        headers = {}
        while True:
            l = await reader.readline()
            l = l.decode()
            if l == '\r\n':
                break
            k, v = l.split(':', 1)
            headers[k] = v.strip()

        cmd = ArrayCommand(method, id=bytes(chunk_id, 'ascii'))
        if cmd.type == ArrayCommand.COMMAND_PUT:
            cmd.length = int(headers['Content-Length'])
            cmd.data = await reader.read(cmd.length)
        LOGGER.info('Send(%s): %s(%s), %s, payload %s bytes' %
                    (client_id, cmd.name, cmd.id, cmd.status_name,
                    str(cmd.length)))

        outq, inq = self.client.clients[client_id]
        await outq.put(cmd)
        cmd = await inq.get()
        # Should have status of success or error, not none after a round-trip.
        assert cmd.status != ArrayCommand.STATUS_NONE

        LOGGER.info('Recv(%s): %s(%s), %s, payload %s bytes' %
                    (client_id, cmd.name, cmd.id, cmd.status_name,
                    str(cmd.length)))
        if cmd.status == ArrayCommand.STATUS_SUCCESS:
            await start_response(writer, status=200,
                                 headers={'Content-Length': cmd.length})
            if cmd.type == ArrayCommand.COMMAND_GET:
                writer.write(cmd.data)
        else:
            await start_response(writer, status=503)
        writer.write_eof()
        writer.close()


class ArrayClient(object):
    def __init__(self):
        self.clients = {}

    async def handle(self, websocket, path):
        name = await websocket.recv()
        try:
            name = uuid.UUID(bytes=name)
        except ValueError as e:
            LOGGER.debug(e)
            websocket.close()
        LOGGER.info('Connect: {0}'.format(name))
        try:
            inq, outq = self.clients.setdefault(name, (asyncio.Queue(),
                                                       asyncio.Queue()))
            while True:
                cmd = await inq.get()
                try:
                    await asyncio.wait_for(websocket.send(bytes(cmd)), 5)
                    r = await asyncio.wait_for(websocket.recv(), 10)
                    cmd = ArrayCommand.decode(bytes(r, 'ascii'))
                except Exception as e:
                    LOGGER.exception(e)
                    cmd.status = ArrayCommand.STATUS_ERROR
                    cmd.length = 0
                    cmd.data = ''
                await outq.put(cmd)
        # TODO: client is disconnecting, but we don't know it.
        finally:
            try:
                websocket.close()
            except Exception as e:
                LOGGER.exception(e)
            self.clients.pop(name, None)
            LOGGER.info('Disconnect: {0}'.format(name))


class Command(BaseCommand):
    help = """HTTP to Websocket gateway.

    Accepts connections from websocket clients and HTTP clients. Allows HTTP
    clients to issue commands to specific ws clients then proxies the command/
    response."""

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8765,
                            help='Server port')
        parser.add_argument('--bind', default='localhost',
                            help='Server address to bind')

    def handle(self, *args, **kwargs):
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)

        client = ArrayClient()
        server = ArrayServer(client)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            websockets.serve(client.handle, 'localhost', 8765))
        loop.run_until_complete(
            asyncio.start_server(server.handle, 'localhost', 8081))
        loop.run_forever()
