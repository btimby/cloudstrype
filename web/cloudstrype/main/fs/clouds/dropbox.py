import json
import logging

from main.fs import Chunk
from main.fs.clouds.base import OAuth2APIClient
from main.models import BaseStorage


LOGGER = logging.getLogger(__name__)


class DropboxAPIClient(OAuth2APIClient):
    """
    OAuth2 API client for Dropbox.

    Dropbox is a breeze. Their API works as advertised, I have yet to encounter
    an error. Initially I had problems getting the correct MIME types for the
    various endpoints, but this was documented and likely implementor error.

    One thing to note is that we need to document the procedure for disabling
    sync on the .cloudstrype directory.
    """

    PROVIDER = BaseStorage.PROVIDER_DROPBOX
    PROFILE_FIELDS = {
        'uid': 'account_id',
        'email': 'email',
        'name': ['name', 'display_name'],
        'size': ['allocation', 'allocated'],
        'used': 'used',
    }

    AUTHORIZATION_URL = 'https://www.dropbox.com/1/oauth2/authorize'
    ACCESS_TOKEN_URL = 'https://api.dropbox.com/1/oauth2/token'
    REFRESH_TOKEN_URL = None

    USER_PROFILE_URL = \
        ('post', 'https://api.dropbox.com/2/users/get_current_account')
    USER_STORAGE_URL = \
        ('post', 'https://api.dropboxapi.com/2/users/get_space_usage')

    DOWNLOAD_URL = ('post', 'https://content.dropboxapi.com/2/files/download')
    UPLOAD_URL = ('post', 'https://content.dropboxapi.com/2/files/upload')
    DELETE_URL = ('post', 'https://api.dropboxapi.com/2/files/delete')

    def request(self, method, url, chunk, headers={}, **kwargs):
        headers['Dropbox-API-Arg'] = json.dumps({
            'path': '/.cloudstrype/%s/%s' % (self.oauth_access.user.uid,
                                             chunk.uid),
        })
        return super().request(method, url, chunk, headers=headers, **kwargs)

    def upload(self, chunk, data, headers={}, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        headers['Content-Type'] = 'application/octet-stream'
        return super().upload(chunk, headers=headers, data=data, **kwargs)

    def delete(self, chunk, **kwargs):
        headers = {
            'Content-Type': 'application/json'
        }
        super().delete(chunk, headers=headers,
                       data=json.dumps({'path': '/%s' % chunk.uid}), **kwargs)
