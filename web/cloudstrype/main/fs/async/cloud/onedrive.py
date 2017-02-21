import json
import logging

from .base import OAuthProvider


LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler())


class OnedriveProvider(OAuthProvider):
    @property
    def DOWNLOAD_URL(self):
        return ('get', 'https://api.onedrive.com/v1.0/drive/root:/{path}:/content')

    @property
    def UPLOAD_URL(self):
        return ('put', 'https://api.onedrive.com/v1.0/drive/root:/{path}:/content')

    @property
    def DELETE_URL(self):
        return ('delete', 'https://api.onedrive.com/v1.0/drive/root:/{path}')

    async def _request(self, method, url, chunk, headers={}, **kwargs):
        """
        Make connection for Dropbox.

        Uses _request(), which is provided by OAuthProvider and HTTPProvider.
        """
        url = url.format(path=chunk.id)
        return await super()._request(method, url, chunk, headers=headers,
                                      **kwargs)
