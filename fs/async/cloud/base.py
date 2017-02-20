import json
import logging

import abc
import aiohttp


LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler())


class HTTPProvider:
    __metaclass__ = abc.ABCMeta

    def __init__(self, connection):
        self.connection = connection

    @abc.abstractproperty
    def DOWNLOAD_URL(self):
        pass

    @abc.abstractproperty
    def UPLOAD_URL(self):
        pass

    async def _request(self, method, url, id, headers={}):
        """
        Perform HTTP request.
        """
        return await aiohttp.request(
            method, url, headers=headers, skip_auto_headers=['Content-Type'])

    def read(self, id):
        return self._request(*self.DOWNLOAD_URL, id)

    def write(self, id, data):
        r = self._request(*self.UPLOAD_URL, id)
        r.write(data)


class OAuthProvider(HTTPProvider):
    def __init__(self, connection):
        super().__init__(connection)
        self.access_token = connection.get('token')

    def _request(self, method, url, id, headers={}):
        """
        Perform HTTP request for OAuth.
        """
        headers['Authorization'] = 'Bearer %s' % self.access_token
        return super()._request(method, url, id, headers)
