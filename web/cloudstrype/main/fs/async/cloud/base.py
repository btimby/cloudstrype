import abc
import aiohttp
import json
import logging


LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler())


class BaseProvider(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    async def download(self, id):
        return

    @abc.abstractmethod
    async def upload(self, id, data):
        return

    @abc.abstractmethod
    async def delete(self, id):
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

    async def _request(self, method, url, id, headers={}):
        """
        Perform HTTP request.
        """
        return await aiohttp.request(
            method, url, headers=headers, skip_auto_headers=['Content-Type'])

    async def download(self, id):
        return self._request(*self.DOWNLOAD_URL, id)

    async def upload(self, id, data):
        headers = {
            'Content-Type': 'application/octet-stream',
        }
        r = self._request(*self.UPLOAD_URL, id, headers=headers)
        r.write(data)

    async def delete(self, id):
        return self._request(*self.DOWNLOAD_URL, id)


class OAuthProvider(HTTPProvider):
    def __init__(self, connection):
        super().__init__(connection)
        self.access_token = connection.get('token')

    async def _request(self, method, url, id, headers={}):
        """
        Perform HTTP request for OAuth.
        """
        headers['Authorization'] = 'Bearer %s' % self.access_token
        return super()._request(method, url, id, headers)
