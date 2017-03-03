import json
import logging

from main.fs import Chunk
from main.fs.clouds import OAuth2APIClient
from main.models import OAuth2Provider


LOGGER = logging.getLogger(__name__)


class DropboxAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_DROPBOX
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


class OnedriveAPIClient(OAuth2APIClient):
    SCOPES = [
        'wl.basic', 'onedrive.readwrite', 'offline_access', 'wl.emails',
    ]
    PROVIDER = OAuth2Provider.PROVIDER_ONEDRIVE
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': ['emails', 'account'],
        'name': 'name',
        'size': ['quota', 'total'],
        'used': ['quota', 'used'],
    }

    AUTHORIZATION_URL = 'https://login.live.com/oauth20_authorize.srf'
    ACCESS_TOKEN_URL = 'https://login.live.com/oauth20_token.srf'
    REFRESH_TOKEN_URL = 'https://login.live.com/oauth20_token.srf'

    USER_PROFILE_URL = ('get', 'https://apis.live.net/v5.0/me')
    USER_STORAGE_URL = ('get', 'https://api.onedrive.com/v1.0/drive')

    DOWNLOAD_URL = \
        ('get', 'https://api.onedrive.com/v1.0/drive/root:/{path}:/content')
    UPLOAD_URL = \
        ('put', 'https://api.onedrive.com/v1.0/drive/root:/{path}:/content')
    DELETE_URL = \
        ('delete', 'https://api.onedrive.com/v1.0/drive/root:/{path}')

    def request(self, method, url, chunk, headers={}, **kwargs):
        url = url.format(
            path='.cloudstrype/%s/%s' % (self.oauth_access.user.uid,
                                         chunk.uid))
        return super().request(method, url, chunk, headers=headers, **kwargs)
