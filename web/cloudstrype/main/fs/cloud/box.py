import json
import logging

from io import BytesIO

from main.fs.async import Chunk
from main.fs.async.cloud.base import (
    OAuthProvider, HTTPError
)


LOGGER = logging.getLogger(__file__)
LOGGER.setLevel(logging.DEBUG)
LOGGER.addHandler(logging.StreamHandler())


class BoxProvider(OAuthProvider):
    @property
    def DOWNLOAD_URL(self):
        return ('get', 'https://api.box.com/2.0/files/{file_id}/content')

    @property
    def UPLOAD_URL(self):
        return ('post', 'https://upload.box.com/api/2.0/files/content')

    @property
    def DELETE_URL(self):
        return ('delete', 'https://api.box.com/2.0/files/{file_id}')

    async def upload(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        data = {
            'attributes': json.dumps({'name': chunk.id, 'parent': {'id': 0}}),
            'file': BytesIO(chunk.data),
        }
        tries = 0
        while True:
            tries += 1
            try:
                r = await self._request(*self.UPLOAD_URL, chunk, data=data)
                break
            except HTTPError as e:
                if tries < 3 and e.response.status == 409:
                    # 409 means a file with that name exists...
                    error = await e.response.json()
                    # Grab the id of the existing file...
                    chunk.clouds.setdefault(self.id, {})['file_id'] = \
                        error['context_info']['conflicts']['id']
                    # And delete it...
                    await self.delete(chunk)
                    # Then try again.
                    continue
                raise
        attrs = await r.json()
        chunk.clouds[self.id] = {'file_id': attrs['entries'][0]['id']}
        r.close()

    async def download(self, chunk):
        method, url = self.DOWNLOAD_URL
        url = url.format(file_id=chunk.clouds[self.id]['file_id'])
        r = await self._request(method, url, chunk)
        chunk.data = await r.read()

    async def delete(self, chunk):
        method, url = self.DELETE_URL
        url = url.format(file_id=chunk.clouds[self.id]['file_id'])
        r = await self._request(method, url, chunk)
        r.close()
