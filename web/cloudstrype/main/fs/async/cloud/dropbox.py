import json
import logging

from .base import OAuthProvider


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
        return ('post', 'https://content.dropboxapi.com/2/files/delete')

    def _request(self, method, url, id, headers={}):
        """
        Make connection for Dropbox.

        Uses _request(), which is provided by OAuthProvider and HTTPProvider.
        """
        headers['Dropbox-API-Arg'] = json.dumps({'path': id})
        return super()._request(method, url, id, headers)

    async def delete(self, id):
        headers = {
            'Content-Type': 'application/octet-stream',
        }
        r = await self._request(*self.DOWNLOAD_URL, id, headers=headers)
        r.write(json.dumps({'path': id}))
