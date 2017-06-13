"""
Handle communication with Array clients.

Presents HTTP interface for communication with long-lived Array clients.
Clients connect and register with the server. HTTP requests are dispatched to
the connected clients via private queues. The responses are routed back to the
requestor.
"""

import asyncio
import json
import logging
import struct
import time
import uuid

from urllib.parse import parse_qs
from collections import namedtuple

from django.core.management.base import BaseCommand

# from main.models import Storage


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())

HTTP_STATUS = {
    200: b'OK',
    404: b'NOT FOUND',
    503: b'UNAVAILABLE',
}
HTML_ERROR = b'<html><body>%b</body></html>'


Request = namedtuple('Request', ('method', 'path', 'querystring', 'headers',
                     'reader'))


class RequestError(Exception):
    def __init__(self, message=None, status=500):
        self.status = status
        super().__init__('HTTP %s Status: ' % (status, message))


class ServerError(RequestError):
    pass


async def start_response(writer, content_type='text/html', status=None,
                         headers={}, exception=None):
    """
    Low level HTTP response.

    Writes HTTP response.
    """
    if exception and status is None:
        status = exception.status
    elif status is None:
        status = 200
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
    """
    Low level HTTP Error.

    Write an HTTP error response.
    """
    body = HTML_ERROR % message
    await start_response(
        writer, status=status, headers={'Content-Length': len(body)})

    writer.write(body)
    await writer.drain()
    writer.close()


async def parse_request(reader, writer):
    """
    Low level HTTP request parsing.

    Parses HTTP request, returns a Request object.
    """
    try:
        request = await reader.readline()
        if request == b'':
            LOGGER.debug("Empty request")
            writer.close()
            raise ServerError('Empty request', status=500)

        method, path, http = request.decode().split()
        assert method in ('GET', 'PUT', 'DELETE')
        assert http == 'HTTP/1.1'

        try:
            path, querystring = path.split('?', 1)
        except ValueError as e:
            querystring = {}
        else:
            querystring = parse_qs(querystring)

        try:
            # Parse headers.
            headers = {}
            while True:
                l = await reader.readline()
                l = l.decode()
                if l == '\r\n':
                    break
                k, v = l.split(':', 1)
                headers[k] = v.strip()
        except Exception as e:
            raise ServerError(str(e), 500)

        return Request(method, path, querystring, headers, reader)
    except RequestError:
        return


# Kept as an example.
# async def update_stat(name, size, used):
#     """
#     Coroutine to run database update in executor.
#     """
#
#     def _update():
#         try:
#             storage = Storage.objects.get(
#                 type=Storage.TYPE_ARRAY, attrs__name=str(name))
#             storage.size, storage.used = size, used
#             storage.save(update_fields=['size', 'used'])
#         except Exception as e:
#             LOGGER.exception(e)
#
#     asyncio.get_event_loop().run_in_executor(None, _update)


class ArrayCommand(object):
    """
    Message format.

    Written over the wire and stored in queues. This is the message handling
    class for communication between us and the array client. It represents both
    requests and responses.

    Represents a command, status, optional id and optional data.

    Handles serialization and deserialization.

    The wire format is:
        [
            command(byte),
            status(byte),
            id_len(int),
            data_len(int),
            id(str),
            data(?)
        ]
    """

    COMMAND_GET = 0
    COMMAND_PUT = 1
    COMMAND_DELETE = 2
    COMMAND_PING = 3
    COMMAND_STAT = 4

    COMMAND_NAMES = {
        COMMAND_GET: 'GET',
        COMMAND_PUT: 'PUT',
        COMMAND_DELETE: 'DELETE',
        COMMAND_PING: 'PING',
        COMMAND_STAT: 'STAT',
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

    FORMAT = '<bbii'

    def __init__(self, type, status=STATUS_NONE, idlen=None, datalen=None,
                 id=None, data=None):
        if isinstance(type, str):
            # Convert HTTP method string to integer.
            type = self.COMMAND_TYPES[type]
        assert type in self.COMMAND_NAMES.keys()
        assert status in self.STATUS_NAMES.keys()
        self.type = type
        self.status = status
        self.idlen = 0 if idlen is None else idlen
        self.datalen = 0 if datalen is None else datalen
        self._id, self._data = b'', b''
        if id is not None:
            self.id = id
        if data is not None:
            self.data = data

    def _get_id(self):
        return self._id

    def _set_id(self, value):
        self.idlen = len(value)
        self._id = value

    id = property(_get_id, _set_id)

    def _get_data(self):
        return self._data

    def _set_data(self, value):
        self.datalen = len(value)
        self._data = value

    data = property(_get_data, _set_data)

    @property
    def length(self):
        """Combined length of "payload"."""
        return self.idlen + self.datalen

    @property
    def header(self):
        """Serialize header."""
        return struct.pack(self.FORMAT, self.type, self.status, self.idlen,
                           self.datalen)

    def __bytes__(self):
        """Serialize command."""
        assert len(self.id) == self.idlen
        assert len(self.data) == self.datalen
        return self.header + self.id + self.data

    @staticmethod
    def decode_header(buffer):
        """Deserialize header."""
        type, status, idlen, datalen = struct.unpack(ArrayCommand.FORMAT,
                                                     buffer)
        return ArrayCommand(type, status, idlen, datalen)

    @property
    def type_name(self):
        """Convert command type to string."""
        return self.COMMAND_NAMES[self.type]

    @property
    def status_name(self):
        """Convert command status to string."""
        return self.STATUS_NAMES[self.status]


class ArrayClient(object):
    """A connected Array client."""

    def __init__(self):
        self.inq, self.outq = (asyncio.Queue(2), asyncio.Queue(2))
        self.last = time.time()
        self.total = 0


# TODO: Look into aiohttp low-level server.
class ArrayServer(object):
    """
    Array server.

    Cloudstrype web application <-HTTP-> Array Server <-tcp/ip-> Array Client

    Allows Cloudstrype web application to interface with array clients via an
    HTTP interface. Allows Array Clients to maintain long-lived connections.
    Commands received via HTTP from Cloudstrype web will be dispatched to
    awaiting clients. Clients will process the commands, reply and the reply is
    relayed back to Cloudstrype web.
    """

    def __init__(self):
        self.clients = {}

    def gather_stats(self):
        stats = {}
        clients = stats['clients'] = {}
        for name, client in self.clients.items():
            clients[name] = {
                'queues': {
                    'out': client.outq.qsize(),
                    'in': client.inq.qsize(),
                },
                'last': client.last,
                'total': client.total,
            }
        return stats

    async def handle_http(self, reader, writer):
        """
        Handle the HTTP side of the server.

        HTTP clients send us REST-like requests for chunks. We dispatch them to
        array clients on the other side.
        """
        try:
            request = await parse_request(reader, writer)
        except RequestError as e:
            await error_response(writer, e.status, e.message)
            return

        if request.path == '/api/stats':
            await self.handle_api(request, writer)
        else:
            await self.handle_chunk(request, writer)

        writer.write_eof()
        await writer.drain()
        writer.close()

    async def handle_chunk(self, request, writer):
        """
        Handle a chunk GET/PUT/DELETE request.

        Determine client, build a command struct and place it into the client's
        queue. Await a reply and send it to the requester.
        """
        # path == <client GUID>/<chunk ID>
        try:
            client_id, chunk_id = request.path.strip('/').split('/', 1)
        except ValueError as e:
            LOGGER.debug('%s: %s', e, request.path, exc_info=True)
            await error_response(writer, 404, b'Not Found')
            raise RequestError()

        try:
            client_id = uuid.UUID(client_id)
        except ValueError as e:
            LOGGER.debug('%s: %s', e, client_id, exc_info=True)
            await error_response(writer, 404, b'Not Found')
            raise RequestError()

        cmd = ArrayCommand(request.method, id=bytes(chunk_id, 'ascii'))
        if cmd.type == ArrayCommand.COMMAND_PUT:
            cmd.data = await request.reader.read(
                int(request.headers['Content-Length']))

        LOGGER.info(
            'Send({0}): {1.type_name}({1.id}), {1.status_name}, id {1.idlen} '
            'bytes, payload {1.datalen} bytes'.format(client_id, cmd))

        try:
            client = self.clients[client_id]
        except KeyError:
            LOGGER.debug('%s not in (%s)' % (client_id,
                                             list(self.clients.keys())))
            raise RequestError(b'Not Found', 404)

        # Send the command to the array client.
        try:
            # Purposefully omitted await, this function executes immediately.
            client.outq.put_nowait(cmd)
        except asyncio.QueueFull as e:
            raise RequestError(str(e))

        # Wait for response. Should probably timeout on the get().
        cmd = await client.inq.get()

        # Should have status of success or error, not none after a round-trip.
        assert cmd.status != ArrayCommand.STATUS_NONE, 'Invalid status'

        LOGGER.info(
            'Recv({0}): {1.type_name}({1.id}), {1.status_name}, id {1.idlen} '
            'bytes, payload {1.datalen} bytes'.format(client_id, cmd))

        if cmd.status == ArrayCommand.STATUS_SUCCESS:
            await start_response(writer, status=200,
                                 headers={'Content-Length': cmd.datalen})
            if cmd.type == ArrayCommand.COMMAND_GET:
                writer.write(cmd.data)
        else:
            await start_response(writer, status=503)

    async def handle_api(self, request, writer):
        body = json.dumps(self.gather_stats())
        await start_response(writer, content_type='text/json', status=200,
                             headers={'Content-Length': len(body)})
        writer.write(body)

    async def handle_client(self, reader, writer):
        """
        Handle the array side of the server.

        Here we maintain an open connection with all the array clients, and
        send commands when they arrive. Periodically, we send a PING command as
        a simple keepalive.
        """
        name = await reader.read(16)
        try:
            name = uuid.UUID(bytes=name)
        except ValueError as e:
            LOGGER.warning(e, exc_info=True)
            writer.close()
            return
        LOGGER.info('Connect: {0}'.format(name))

        try:
            # Set up bidirectional queues for message passing with HTTP
            # clients.
            try:
                client = self.clients[name]
            except KeyError:
                client = self.clients[name] = ArrayClient()

            # Queue up a STAT command.
            await client.inq.put(ArrayCommand(ArrayCommand.COMMAND_STAT))

            while True:
                try:
                    cmd = await asyncio.wait_for(client.inq.get(), 30)
                except asyncio.TimeoutError:
                    LOGGER.debug('No command, doing keepalive')
                    cmd = ArrayCommand(ArrayCommand.COMMAND_PING)

                try:
                    # Write command to client.
                    LOGGER.debug('Sending {0.length} bytes'.format(cmd))
                    writer.write(bytes(cmd))
                    await asyncio.wait_for(writer.drain(), 5)

                    # Read client response.
                    buffer = await asyncio.wait_for(
                        reader.read(struct.calcsize(ArrayCommand.FORMAT)), 5)
                    # Decode header.
                    cmd = ArrayCommand.decode_header(buffer)

                    # Decode body (if present) and handle response.
                    if cmd.length:
                        # If command has a payload, get it.
                        buffer = await asyncio.wait_for(
                            reader.read(cmd.length), 10)
                        cmd.id = buffer[:cmd.idlen]
                        cmd.data = buffer[cmd.idlen:]
                        LOGGER.debug('Payload %s bytes, data %s bytes',
                                     cmd.length, cmd.datalen)
                    if cmd.type == ArrayCommand.COMMAND_STAT:
                        # Handle stat command by saving reported size and bytes
                        # used.
                        client.size, client.used = \
                            struct.unpack('qq', cmd.data)
                        LOGGER.debug(
                            'Using %s bytes of %s', client.used, client.size)

                    LOGGER.debug('Received {0.length} bytes'.format(cmd))

                except Exception as e:
                    LOGGER.exception(e)
                    # Create error response to (maybe) push back to the HTTP
                    # side.
                    cmd.status = ArrayCommand.STATUS_ERROR
                    cmd.data = ''
                    # Consider all exceptions fatal. We can catch more specific
                    # ones above and treat them as non-fatal.
                    break

                finally:
                    client.last = time.time()
                    client.total += 1
                    # PING & STAT commands did not originate from the queue, so
                    # no need to return them to HTTP side.
                    if cmd.type not in (ArrayCommand.COMMAND_PING,
                                        ArrayCommand.COMMAND_STAT):
                        await client.outq.put(cmd)

        finally:
            try:
                writer.close()
            except Exception as e:
                LOGGER.exception(e)
            try:
                del clients[name]
            except KeyError:
                pass
            LOGGER.info('Disconnect: {0}'.format(name))


class Command(BaseCommand):
    help = """HTTP to socket gateway.

    Accepts connections from socket clients and HTTP clients. Allows HTTP
    clients to issue commands to specific clients then relays the response."""

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8765,
                            help='Server port')
        parser.add_argument('--http-port', type=int, default=8001,
                            help='HTTP server port')
        parser.add_argument('--bind', default='localhost',
                            help='Server address to bind')

    def handle(self, *args, bind='localhost', port=8765, http_port=8001,
               **kwargs):
        LOGGER.addHandler(logging.StreamHandler())
        LOGGER.setLevel(logging.DEBUG)

        server = ArrayServer()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            asyncio.start_server(server.handle_client, bind, port))
        loop.run_until_complete(
            asyncio.start_server(server.handle_http, bind, http_port))
        loop.run_forever()
