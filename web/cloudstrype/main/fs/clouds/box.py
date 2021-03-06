import json
import logging

from io import BytesIO

from main.fs.clouds.base import BaseOAuth2APIClient, HTTPError
from main.models import Chunk, Storage


LOGGER = logging.getLogger(__name__)


class BoxAPIClient(BaseOAuth2APIClient):
    """
    OAuth2 API client for Box.

    The Box API does not seem well-designed. It makes some common operations
    quite difficult. They are also _very_ particular about OAuth access tokens.
    I seem to get expired token errors every other day, while the other
    providers just rotate (refresh) keys as expected.

    It is possible this is due to my development machine, requests are being
    cancelled as the web app restarts due to code changes etc, so it is not
    the most stable environment, but Box is the only provider having token
    problems so I am not sure.

    For us, we can just have the user perform the OAuth2 3-legged auth flow
    to refresh our key set, but what a PiTA.
    """

    TYPE = Storage.TYPE_BOX
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': 'login',
        'name': 'name',
        'size': 'space_amount',
        'used': 'space_used',
    }

    AUTHORIZATION_URL = 'https://account.box.com/api/oauth2/authorize'
    ACCESS_TOKEN_URL = 'https://api.box.com/oauth2/token'
    REFRESH_TOKEN_URL = 'https://api.box.com/oauth2/token'

    USER_PROFILE_URL = ('get', 'https://api.box.com/2.0/users/me')
    USER_STORAGE_URL = None

    DOWNLOAD_URL = ('get', 'https://api.box.com/2.0/files/{file_id}/content')
    UPLOAD_URL = ('post', 'https://upload.box.com/api/2.0/files/content')
    DELETE_URL = ('delete', 'https://api.box.com/2.0/files/{file_id}')

    CREATE_URL = 'https://api.box.com/2.0/folders'

    def download(self, chunk, **kwargs):
        "Overidden to add file_id to URL."
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storages.get(
            storage__type=self.TYPE)
        method, url = self.DOWNLOAD_URL
        url = url.format(file_id=chunk_storage.attrs['file.id'])
        r = self.request(method, url, chunk, **kwargs)
        return r.content

    def upload(self, chunk, data, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        parent_id = self.storage.attrs['root.id']
        kwargs['data'] = {
            'attributes': json.dumps({
                'name': chunk.uid, 'parent': {'id': parent_id}
            }),
        }
        kwargs['files'] = {
            'file': (chunk.uid, BytesIO(data), 'text/plain'),
        }
        tried_delete = False
        while True:
            r = self.request(self.UPLOAD_URL[0], self.UPLOAD_URL[1], chunk,
                             **kwargs)
            if not tried_delete and r.status_code == 409:
                # If there is a conflict, delete the file and continue to try
                # to upload again. tried_delete is used to ensure we only
                # repeat this loop once before exiting with error or success.
                method, url = self.DELETE_URL
                url = url.format(
                    file_id=r.json()['context_info']['conflicts']['id'])
                r = self.request(method, url, chunk)
                tried_delete = True
                continue
            if not 199 < r.status_code < 300:
                raise HTTPError(response=r)
            else:
                break
        attrs = r.json()
        # Store the file_id provided by Box into the attribute store of
        # ChunkStorage
        try:
            return {'file.id': attrs['entries'][0]['id']}
        except KeyError as e:
            LOGGER.error('key "%s" not in response "%s"', e.args[0], attrs)
            raise
        except IndexError as e:
            LOGGER.error('result was empty "%s"', attrs)
            raise

    def delete(self, chunk, **kwargs):
        "Overidden to add file_id to URL."
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storages.get(
            storage__type=self.TYPE)
        method, url = self.DELETE_URL
        url = url.format(file_id=chunk_storage.attrs['file.id'])
        r = self.request(method, url, chunk, **kwargs)
        r.close()

    def get_profile(self, **kwargs):
        "Overidden to fetch profile and storage in one request."
        profile = self.oauthsession.request(
            *self.USER_PROFILE_URL, **kwargs).json()

        return self._get_profile_fields(profile, 'uid', 'email', 'name',
                                        'size', 'used')

    def initialize(self, storage):
        """
        Overidden to create a storage location.

        We create a storage directory for Cloudstrype, and store it's id so we
        can upload to it later.
        """
        # "0" root directory, our first goes under that, sencond under first.
        parent_id, kwargs = "0", {}
        for name in ('.cloudstrype', storage.user.uid):
            kwargs['data'] = json.dumps({
                'name': name,
                'parent': {
                    'id': parent_id,
                },
            })
            # Create the directory:
            r = self.oauthsession.post(self.CREATE_URL, **kwargs)
            attrs = r.json()
            if r.status_code == 409:
                # The directory exists, so nab it's ID, and continue to child.
                parent_id = attrs['context_info']['conflicts'][0]['id']
            else:
                # We created it, so nab the ID and continue to child.
                parent_id = r.json()['id']
        storage.attrs = storage.attrs or {}
        storage.attrs.update({'root.id': parent_id})
