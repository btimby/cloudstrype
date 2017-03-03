import json

from datetime import datetime, timedelta
from io import BytesIO
from inspect import isclass

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError

from django.utils import timezone
from django.utils.dateformat import format

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
    def get_client(cls, provider, oauth_access=None, oauth_storage=None,
                   **kwargs):
        provider_cls = cls
        for item in globals().values():
            if isclass(item) and issubclass(item, cls) and \
               getattr(item, 'PROVIDER', None) == \
               provider.provider:
                provider_cls = item
                break
        else:
            raise ValueError('Invalid provider')
        return provider_cls(provider, oauth_access=oauth_access,
                            oauth_storage=oauth_storage, **kwargs)

    def __init__(self, provider, oauth_access=None, oauth_storage=None,
                 redirect_uri=None, **kwargs):
        self.provider = provider
        self.oauth_access = oauth_access
        self.oauth_storage = oauth_storage
        if self.oauth_access:
            token = {
                'access_token': self.oauth_access.access_token,
                'refresh_token': self.oauth_access.refresh_token,
            }
            if self.oauth_access.expires:
                token['expires_at'] = format(self.oauth_access.expires, 'U')
            # self.oauthsession = OAuth2Session(
            #     token=token, auto_refresh_url=self.REFRESH_TOKEN_URL,
            #     token_updater=self._refresh_token_callback, **kwargs)
            self.oauthsession = OAuth2Session(token=token, **kwargs)
        else:
            self.oauthsession = OAuth2Session(
                provider.client_id, redirect_uri=redirect_uri,
                scope=self.SCOPES, **kwargs)

    def _refresh_token_callback(self, token):
        "Called by OAuth2Session when a token is refreshed."
        if 'expires_at' in token:
            expires = datetime.fromtimestamp(token['expires_at'],
                                             timezone.utc)
        elif 'expires_in' in token:
            expires = datetime.now(timezone.utc) + \
                      timedelta(seconds=token['expires_in'])
        else:
            expires = None
        self.oauth_access.access_token = token['access_token']
        self.oauth_access.refresh_token = token['refresh_token']
        self.expires = expires
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

    # def request(self, method, url, chunk, headers={}, **kwargs):
    #     """
    #     Perform HTTP request for OAuth.
    #     """
    #     return self.oauthsession.request(method, url, headers=headers,
    #                                      **kwargs)
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
                self._refresh_token_callback(token)
                continue

    def download(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(self.DOWNLOAD_URL[0], self.DOWNLOAD_URL[1], chunk,
                         **kwargs)
        return r.content

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

    def initialize(self):
        """
        Allow the storage provider to initialize the account.

        For some providers, this means creating a location in which to store
        our files. Some providers require a parent ID to upload to, so at this
        point we can store that in the attributes of the OAuth2StorageToken
        instance.
        """
        pass


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
                self._refresh_token_callback(token)
                continue

    def download(self, chunk, **kwargs):
        "Overidden to add file_id to URL."
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        method, url = self.DOWNLOAD_URL
        url = url.format(file_id=chunk_storage.attrs['file_id'])
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
        attrs = r.json()
        # Store the file_id provided by Box into the attribute store of
        # ChunkStorage
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        chunk_storage.attrs = {'file.id': attrs['entries'][0]['id']}
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

    CREATE_URL = 'https://www.googleapis.com/drive/v2/files'

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
        try:
            parent_id = self.oauth_storage.attrs.get('root.id')
        except ValueError:
            parent_id = None
        attrs = {
            'mimeType': 'text/plain',
            'title': chunk.uid,
            'description': 'Cloudstrype chunk',
        }
        if parent_id:
            attrs['parents'] = [{'id': parent_id}]
        kwargs['files'] = {
            'data': ('metadata', json.dumps(attrs), 'application/json'),
            'file': (chunk.uid, BytesIO(data), 'text/plain'),
        }
        method, url = self.UPLOAD_URL
        url += '?uploadType=multipart'
        r = self.request(method, url, chunk, **kwargs)
        attrs = r.json()
        # Store the file ID provided by Google into the attribute store of
        # ChunkStorage
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        chunk_storage.attrs = {'file.id': attrs['id']}
        chunk_storage.save()
        r.close()

    def delete(self, chunk, **kwargs):
        "Overidden to add file_id to URL."
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        method, url = self.DELETE_URL
        url = url.format(file_id=chunk_storage.attrs['file_id'])
        r = self.request(method, url, chunk, **kwargs)
        r.close()

    def authorization_url(self):
        "Overidden to add access_type=offline."
        return self.oauthsession.authorization_url(
            self.AUTHORIZATION_URL, access_type='offline')

    def initialize(self):
        """
        Overidden to create a storage location.

        We create a storage directory for Cloudstrype, and store it's id so we
        can upload to it later.

        Unlike the Box API (which also requires this nonsense) Google does not
        report a conflict for items with the SAME NAME. I guess I am too
        stoopid to understand why I would want two things with the same name.
        Anyway, we have to do a round-trip to check existence first, otherwise
        we will create duplicates, which would be even stoopider.

        So, this means we make *FOUR* api calls to initialze our directory.
        """
        # Omit parent to put file in root. Provide first's ID to place second
        # inside it.
        parent_id, kwargs = None, {
            'headers': {'Content-Type': 'application/json'}
        }
        for name in ('.cloudstrype', self.oauth_access.user.uid):
            # Hey Google, fuck you for making me do this!
            query = [
                "title='%s'" % name,
            ]
            if parent_id:
                query.append("'%s' in parents" % parent_id)
            params = {
                'q': ' and '.join(query),
            }
            r = self.oauthsession.get(self.CREATE_URL, params=params)
            if r.status_code == 200:
                parent_id = r.json()['items'][0]['id']
                continue

            # OK, with that extra round-trip out of the way, let's create the
            # missing directory.
            data = {
                'mimeType': 'application/vnd.google-apps.folder',
                'title': name,
                'description': 'Cloudstrype storage',
            }
            if parent_id:
                data['parents'] = [{'id': parent_id}]
            # The body of the request should be our JSON object as string.
            kwargs['data'] = json.dumps(data)
            # Create the directory:
            r = self.oauthsession.post(self.CREATE_URL, **kwargs)
            parent_id = r.json()['id']
        self.oauth_storage.attrs = {'root.id': parent_id}
        self.oauth_storage.save()


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
        "Overidden to provide access_token via querystring."
        return super().get_profile(params=self.oauthsession.token)
