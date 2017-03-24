import uuid
import struct
import asyncio
import logging

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


async def parse_request(reader, writer):
    request = await reader.readline()
    if request == b'':
        LOGGER.debug("Empty request")
        writer.close()
        raise RequestError()

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
        raise RequestError()

    try:
        client_id = uuid.UUID(client_id)
    except ValueError as e:
        LOGGER.debug(e)
        await error_response(writer, 404, b'Not Found')
        raise RequestError()

    # Parse headers.
    headers = {}
    while True:
        l = await reader.readline()
        l = l.decode()
        if l == '\r\n':
            break
        k, v = l.split(':', 1)
        headers[k] = v.strip()

    return method, path, querystring, headers, client_id, chunk_id


class RequestError(Exception):
    pass


class ArrayCommand(object):
    COMMAND_GET = 0
    COMMAND_PUT = 1
    COMMAND_DELETE = 2
    COMMAND_PING = 3

    COMMAND_NAMES = {
        COMMAND_GET: 'GET',
        COMMAND_PUT: 'PUT',
        COMMAND_DELETE: 'DELETE',
        COMMAND_PING: 'PING',
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
        assert type in (self.COMMAND_GET, self.COMMAND_PUT,
                        self.COMMAND_DELETE, self.COMMAND_PING)
        assert status in (self.STATUS_NONE, self.STATUS_SUCCESS,
                          self.STATUS_ERROR)
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
        return self.idlen + self.datalen

    @property
    def header(self):
        return struct.pack(self.FORMAT, self.type, self.status, self.idlen,
                           self.datalen)

    def __bytes__(self):
        assert len(self.id) == self.idlen
        assert len(self.data) == self.datalen
        return self.header + self.id + self.data

    @staticmethod
    def decode_header(buffer):
        type, status, idlen, datalen = struct.unpack(ArrayCommand.FORMAT,
                                                     buffer)
        return ArrayCommand(type, status, idlen, datalen)

    @property
    def type_name(self):
        return self.COMMAND_NAMES[self.type]

    @property
    def status_name(self):
        return self.STATUS_NAMES[self.status]


class ArrayServer(object):
    # TODO: combine with Client class. We can detect the path and "upgrade" to
    # a websocket for certain clients, or handle as HTTP for others.
    def __init__(self):
        self.clients = {}

    async def handle_http(self, reader, writer):
        """
        Handle the HTTP side of the server.

        HTTP clients send us REST-like requests for chunks. We dispatch them to
        array clients on the other side.
        """
        try:
            method, path, querystring, headers, client_id, chunk_id = \
                await parse_request(reader, writer)
        except RequestError:
            return

        cmd = ArrayCommand(method, id=bytes(chunk_id, 'ascii'))
        if cmd.type == ArrayCommand.COMMAND_PUT:
            datalen = int(headers['Content-Length'])
            cmd.data = await reader.read(datalen)

        LOGGER.info(
            'Send({0}): {1.type_name}({1.id}), {1.status_name}, id {1.idlen} '
            'bytes, payload {1.datalen} bytes'.format(client_id, cmd))

        try:
            outq, inq = self.clients[client_id]
        except KeyError:
            LOGGER.debug('%s not in (%s)' % (client_id,
                                             list(self.clients.keys())))
            await error_response(writer, 404, b'Not Found')
            return

        # Send the command to the array client. Wait for their response. Should
        # probably timeout on the get().
        await outq.put(cmd)
        cmd = await inq.get()

        # Should have status of success or error, not none after a round-trip.
        assert cmd.status != ArrayCommand.STATUS_NONE

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

        writer.write_eof()
        await writer.drain()
        writer.close()

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
            LOGGER.debug(e)
            writer.close()
            return
        LOGGER.info('Connect: {0}'.format(name))
        try:
            inq, outq = self.clients.setdefault(name, (asyncio.Queue(),
                                                       asyncio.Queue()))
            while True:
                try:
                    cmd = await asyncio.wait_for(inq.get(), 30)
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
                    cmd = ArrayCommand.decode_header(buffer)
                    if cmd.length:
                        buffer = await asyncio.wait_for(
                            reader.read(cmd.length), 10)
                        cmd.id = buffer[:cmd.idlen]
                        cmd.data = buffer[cmd.idlen:]
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
                    # PING commands did not originate from the queue, so no
                    # need to return them to HTTP side.
                    if cmd.type != ArrayCommand.COMMAND_PING:
                        await outq.put(cmd)
        finally:
            try:
                writer.close()
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

        server = ArrayServer()

        loop = asyncio.get_event_loop()
        loop.run_until_complete(
            asyncio.start_server(server.handle_client, 'localhost', 8765))
        loop.run_until_complete(
            asyncio.start_server(server.handle_http, 'localhost', 8081))
        loop.run_forever()
