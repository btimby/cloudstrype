import json
import logging

from io import BytesIO

from oauthlib.oauth2 import TokenExpiredError

from main.fs import Chunk
from main.fs.clouds import OAuth2APIClient
from main.models import OAuth2Provider


LOGGER = logging.getLogger(__name__)


class BoxAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_BOX
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

    OVERWRITE_URL = ('post', 'https://upload.box.com/api/2.0/files/content')
    CREATE_URL = 'https://api.box.com/2.0/folders'

    def request(self, method, url, chunk, headers={}, **kwargs):
        """
        Perform HTTP request for OAuth.
        """
        while True:
            try:
                return self.oauthsession.request(method, url, headers=headers,
                                                 **kwargs)
            except TokenExpiredError:
                # Do our own, since requests_oaulib is broken.
                token = self.oauthsession.refresh_token(
                    self.REFRESH_TOKEN_URL,
                    refresh_token=self.oauth_access.refresh_token,
                    client_id=self.provider.client_id,
                    client_secret=self.provider.client_secret)
                self._save_refresh_token(token)
                continue

    def download(self, chunk, **kwargs):
        "Overidden to add file_id to URL."
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        method, url = self.DOWNLOAD_URL
        url = url.format(file_id=chunk_storage.attrs['file.id'])
        r = self.request(method, url, chunk, **kwargs)
        return r.content

    def upload(self, chunk, data, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        parent_id = self.oauth_storage.attrs['root.id']
        kwargs['data'] = {
            'attributes': json.dumps({
                'name': chunk.uid, 'parent': {'id': parent_id}
            }),
        }
        kwargs['files'] = {
            'file': (chunk.uid, BytesIO(data), 'text/plain'),
        }
        r = self.request(self.UPLOAD_URL[0], self.UPLOAD_URL[1], chunk,
                         **kwargs)
        if r.status_code == 409:
            # The file exists, make a second POST to overwrite it.
            method, url = self.OVERWRITE_URL
            url = url.format(
                file_id=r.json()['context_info']['conflicts']['id'])
            del kwargs['data']
            r = self.request(method, url, chunk, **kwargs)
        if not 199 < r.status_code < 300:
            raise Exception('%s: "%s"' % (r.status_code, r.text))
        attrs = r.json()
        # Store the file_id provided by Box into the attribute store of
        # ChunkStorage
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        try:
            chunk_storage.attrs = {'file.id': attrs['entries'][0]['id']}
        except KeyError as e:
            LOGGER.error('key "%s" not in response "%s"', e.args[0], attrs)
            raise
        chunk_storage.save()
        return r

    def delete(self, chunk, **kwargs):
        "Overidden to add file_id to URL."
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        method, url = self.DELETE_URL
        url = url.format(file_id=chunk_storage.attrs['file.id'])
        r = self.request(method, url, chunk, **kwargs)
        r.close()

    def get_profile(self, **kwargs):
        "Overidden to fetch profile and storage in one request."
        profile = self.oauthsession.request(
            *self.USER_PROFILE_URL, **kwargs).json()

        uid = self._get_profile_field(profile, 'uid')
        email = self._get_profile_field(profile, 'email')
        name = self._get_profile_field(profile, 'name')
        size = self._get_profile_field(profile, 'size')
        used = self._get_profile_field(profile, 'used')

        return (uid, email, name, size, used)

    def initialize(self):
        """
        Overidden to create a storage location.

        We create a storage directory for Cloudstrype, and store it's id so we
        can upload to it later.
        """
        # "0" root directory, our first goes under that, sencond under first.
        parent_id, kwargs = "0", {}
        for name in ('.cloudstrype', self.oauth_access.user.uid):
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
        self.oauth_storage.attrs = {'root.id': parent_id}
        self.oauth_storage.save()
