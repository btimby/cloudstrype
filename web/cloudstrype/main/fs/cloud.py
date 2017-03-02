import json

from datetime import datetime, timedelta
from io import BytesIO
from inspect import isclass

from requests.exceptions import HTTPError
from requests_oauthlib import OAuth2Session

from django.utils import timezone

from main.fs import Chunk
from main.models import OAuth2Provider


class OAuth2APIClient(object):
    """
    OAuth API client base class.
    """

    SCOPES = []
    PROFILE_FIELDS = {
        'uid': 'uid',
        'email': 'email',
        'name': 'name',
    }
    PROVIDER = None

    AUTHORIZATION_URL = None
    ACCESS_TOKEN_URL = None
    REFRESH_TOKEN_URL = None

    USER_PROFILE_URL = None
    USER_STORAGE_URL = None

    DOWNLOAD_URL = None
    UPLOAD_URL = None
    DELETE_URL = None

    @classmethod
    def get_client(cls, provider, oauth_access=None, **kwargs):
        provider_cls = cls
        for item in globals().values():
            if isclass(item) and issubclass(item, cls) and \
               getattr(item, 'PROVIDER', None) == \
               provider.provider:
                provider_cls = item
                break
        else:
            raise ValueError('Invalid provider')
        return provider_cls(provider, oauth_access=oauth_access, **kwargs)

    def __init__(self, provider, oauth_access=None, redirect_uri=None,
                 **kwargs):
        self.provider = provider
        self.oauth_access = oauth_access
        if self.oauth_access:
            token = {
                'access_token': self.oauth_access.access_token,
                'refresh_token': self.oauth_access.refresh_token
            }
            self.oauthsession = OAuth2Session(
                token=token, auto_refresh_url=self.REFRESH_TOKEN_URL,
                token_updater=self._refresh_token_callback, **kwargs)
        else:
            self.oauthsession = OAuth2Session(
                provider.client_id, redirect_uri=redirect_uri,
                scope=self.SCOPES, **kwargs)

    def _refresh_token_callback(self, token):
        "Called by OAuth2Session when a token is refreshed."
        self.oauth_access.access_token = token
        self.oauth_access.save()

    def _get_profile_field(self, profile, field_name):
        field_name = self.PROFILE_FIELDS[field_name]
        if isinstance(field_name, str):
            return profile.get(field_name)
        else:
            value, field_name = profile, field_name[:]
            while field_name:
                value = value.get(field_name.pop(0))
            return value

    def authorization_url(self, **kwargs):
        return self.oauthsession.authorization_url(self.AUTHORIZATION_URL,
                                                   **kwargs)

    def fetch_token(self, request_uri):
        token = self.oauthsession.fetch_token(
            self.ACCESS_TOKEN_URL, authorization_response=request_uri,
            client_secret=self.provider.client_secret)
        if 'expires_at' in token:
            expires = datetime.fromtimestamp(token['expires_at'],
                                             timezone.utc)
        elif 'expires_in' in token:
            expires = datetime.now(timezone.utc) + \
                      timedelta(seconds=token['expires_in'])
        else:
            expires = None
        return (
            token['access_token'], token.get('refresh_token'), expires
        )

    def get_profile(self, **kwargs):
        profile = self.oauthsession.request(
            *self.USER_PROFILE_URL, **kwargs).json()
        storage = self.oauthsession.request(
            *self.USER_STORAGE_URL, **kwargs).json()

        uid = self._get_profile_field(profile, 'uid')
        email = self._get_profile_field(profile, 'email')
        name = self._get_profile_field(profile, 'name')
        size = self._get_profile_field(storage, 'size')
        used = self._get_profile_field(storage, 'used')

        return (uid, email, name, size, used)

    def request(self, method, url, chunk, headers={}, **kwargs):
        """
        Perform HTTP request for OAuth.
        """
        headers['Authorization'] = 'Bearer %s' % self.oauthsession.access_token
        return self.oauthsession.request(
            method, url, headers=headers, **kwargs)

    def download(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(self.DOWNLOAD_URL[0], self.DOWNLOAD_URL[1], chunk,
                         **kwargs)
        return r.text

    def upload(self, chunk, data, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(self.UPLOAD_URL[0], self.UPLOAD_URL[1], chunk,
                         data=data, **kwargs)
        r.close()

    def delete(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(self.DELETE_URL[0], self.DELETE_URL[1], chunk,
                         **kwargs)
        r.close()


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
        headers['Dropbox-API-Arg'] = json.dumps({'path': '/%s' % chunk.uid})
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
        url = url.format(path=chunk.uid)
        return super().request(method, url, chunk, headers=headers, **kwargs)


class BoxAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_BOX
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': 'login',
        'name': 'name',
    }

    AUTHORIZATION_URL = 'https://account.box.com/api/oauth2/authorize'
    ACCESS_TOKEN_URL = 'https://api.box.com/oauth2/token'
    REFRESH_TOKEN_URL = 'https://api.box.com/oauth2/token'

    USER_PROFILE_URL = ('get', 'https://api.box.com/2.0/users/me')
    USER_STORAGE_URL = None

    DOWNLOAD_URL = ('get', 'https://api.box.com/2.0/files/{file_id}/content')
    UPLOAD_URL = ('post', 'https://upload.box.com/api/2.0/files/content')
    DELETE_URL = ('delete', 'https://api.box.com/2.0/files/{file_id}')

    def request(self, method, url, chunk, headers={}, **kwargs):
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        url = url.format(file_id=chunk_storage.attrs['file_id'])
        return super().request(method, url, chunk, headers=headers, **kwargs)

    def upload(self, chunk, data, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        data = {
            'attributes': json.dumps({'name': chunk.uid, 'parent': {'id': 0}}),
            'file': BytesIO(bytes(data, 'utf-8')),
        }
        tries = 0
        while True:
            tries += 1
            try:
                r = self.request(self.UPLOAD_URL[0], self.UPLOAD_URL[1], chunk,
                                 data=data, **kwargs)
                break
            except HTTPError as e:
                if tries < 3 and e.response.status == 409:
                    # 409 means a file with that name exists...
                    error = e.response.json()
                    # Grab the id of the existing file...
                    chunk.clouds.setdefault(self.id, {})['file_id'] = \
                        error['context_info']['conflicts']['id']
                    # And delete it...
                    self.delete(chunk)
                    # Then try again.
                    continue
                raise
        attrs = r.json()
        # Store the file_id provided by Box into the attribute store of
        # ChunkStorage
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        chunk_storage.attrs['file_id'] = attrs['entries'][0]['id']
        chunk_storage.save()
        return r

    def get_profile(self, **kwargs):
        profile = self.oauthsession.get(self.USER_PROFILE_URL, **kwargs).json()

        uid = self._get_profile_field(profile, 'uid')
        email = self._get_profile_field(profile, 'email'),
        name = self._get_profile_field(profile, 'name')
        size = self._get_profile_field(profile, 'size'),
        used = self._get_profile_field(profile, 'used')

        return (uid, email, name, size, used)


class GDriveAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_GDRIVE
    SCOPES = [
        'profile', 'email', 'https://www.googleapis.com/auth/drive',
    ]
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': 'email',
        'name': 'name',
        'size': 'quotaBytesTotal',
        'used': 'quotaBytesUsed',
    }

    AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    ACCESS_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
    REFRESH_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'

    USER_PROFILE_URL = ('get', 'https://www.googleapis.com/oauth2/v1/userinfo')
    USER_STORAGE_URL = ('get', 'https://www.googleapis.com/drive/v2/about')

    DOWNLOAD_URL = \
        ('GET',
         'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media')
    UPLOAD_URL = \
        ('POST', 'https://www.googleapis.com/upload/drive/v2/files')
    DELETE_URL = \
        ('DELETE', 'https://www.googleapis.com/drive/v2/files/{file_id}')

    def request(self, method, url, chunk, headers={}, **kwargs):
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        url = url.format(file_id=chunk_storage.attrs['file_id'])
        return super().request(method, url, chunk, headers=headers, **kwargs)

    def authoriziation_url(self):
        return self.oauthsession.authorization_url(
            self.AUTHORIZATION_URL, access_type='offline')


class SmartFileAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_SMARTFILE

    AUTHORIZATION_URL = ''
    ACCESS_TOKEN_URL = ''
    REFRESH_TOKEN_URL = None
    USER_PROFILE_URL = ''

    DOWNLOAD_URL = ('get', 'https://app.smartfile.com/api/2/path/data/{path}')
    UPLOAD_URL = ('post', 'https://app.smartfile.com/api/2/path/data/{dir}')
    DELETE_URL = ('delete', 'https://app.smartfile.com/api/2/path/data/{path}')

    def request(self, method, url, chunk, headers={}, **kwargs):
        url = url.format(path=chunk.uid, dir='')
        return super().request(method, url, chunk, headers=headers, **kwargs)


class AmazonClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_AMAZON
    PROFILE_FIELDS = {
        'uid': ['Profile', 'CustomerId'],
        'email': ['Profile', 'PrimaryEmail'],
        'name': ['Profile', 'Name'],
    }
    SCOPES = [
        'profile',
    ]

    AUTHORIZATION_URL = 'https://www.amazon.com/ap/oa'
    ACCESS_TOKEN_URL = 'https://api.amazon.com/auth/o2/token'
    REFRESH_TOKEN_URL = 'https://api.amazon.com/auth/o2/token'
    USER_PROFILE_URL = 'https://www.amazon.com/ap/user/profile'

    def get_profile(self, **kwargs):
        # Amazon wants the access_token in the querystring... Odd...
        return super().get_profile(params=self.oauthsession.token)
