import abc
import aiohttp
import json
import logging

from main.fs.async import Chunk


LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler())


class HTTPError(Exception):
    def __init__(self, response):
        super().__init__('%s: %s' % (response.status, response.reason))
        self.response = response


class BaseProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def download(self, chunk):
        return

    @abc.abstractmethod
    async def upload(self, chunk):
        return

    @abc.abstractmethod
    async def delete(self, chunk):
        return


class HTTPProvider(BaseProvider):
    def __init__(self, id, connection):
        self.id = '%04x' % id
        self.connection = connection

    @abc.abstractproperty
    def DOWNLOAD_URL(self):
        pass

    @abc.abstractproperty
    def UPLOAD_URL(self):
        pass

    @abc.abstractproperty
    def DELETE_URL(self):
        pass

    async def _error(self, response):
        raise HTTPError(response)

    async def _request(self, method, url, chunk, **kwargs):
        """
        Perform HTTP request.
        """
        r = await aiohttp.request(method, url, **kwargs)
        if not 200 <= r.status <= 300:
            await self._error(r)
        return r

    async def download(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = await self._request(*self.DOWNLOAD_URL, chunk)
        chunk.data = await r.read()

    async def upload(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = await self._request(*self.UPLOAD_URL, chunk, data=chunk.data)
        r.close()

    async def delete(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = await self._request(*self.DELETE_URL, chunk)
        r.close()


class OAuthProvider(HTTPProvider):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.token = connection.get('token')

    async def _request(self, method, url, chunk, headers={}, **kwargs):
        """
        Perform HTTP request for OAuth.
        """
        headers['Authorization'] = 'Bearer %s' % self.token
        return await super()._request(method, url, chunk, headers=headers,
                                      **kwargs)
