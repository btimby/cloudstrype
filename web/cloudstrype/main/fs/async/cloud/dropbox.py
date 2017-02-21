import json
import logging

from main.fs.async import Chunk
from main.fs.async.cloud.base import OAuthProvider


LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler())


class DropboxProvider(OAuthProvider):
    @property
    def DOWNLOAD_URL(self):
        return ('post', 'https://content.dropboxapi.com/2/files/download')

    @property
    def UPLOAD_URL(self):
        return ('post', 'https://content.dropboxapi.com/2/files/upload')

    @property
    def DELETE_URL(self):
        return ('post', 'https://api.dropboxapi.com/2/files/delete')

    async def _request(self, method, url, chunk, headers={}, **kwargs):
        """
        Make connection for Dropbox.

        Uses _request(), which is provided by OAuthProvider and HTTPProvider.
        """
        headers['Dropbox-API-Arg'] = json.dumps({'path': '/%s' % chunk.id})
        return await super()._request(method, url, chunk, headers=headers,
                                      skip_auto_headers=['Content-Type'],
                                      **kwargs)

    async def upload(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        headers = {
            'Content-Type': 'application/octet-stream',
        }
        r = await self._request(*self.UPLOAD_URL, chunk, headers=headers,
                                data=chunk.data)
        r.close()

    async def delete(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        headers = {
            'Content-Type': 'application/json'
        }
        r = await super()._request(*self.DELETE_URL, chunk, headers=headers,
                                   skip_auto_headers=['Content-Type'],
                                   data=json.dumps({'path': '/%s' % chunk.id}))
        r.close()
