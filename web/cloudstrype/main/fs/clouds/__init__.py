import logging

from inspect import isclass

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError

from main.fs import Chunk


LOGGER = logging.getLogger(__name__)


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
            # self.oauthsession = OAuth2Session(
            #     token=self.oauth_access.to_dict(), auto_refresh_url=self.REFRESH_TOKEN_URL,  # NOQA
            #     token_updater=self._save_refresh_token, **kwargs)
            self.oauthsession = OAuth2Session(
                token=self.oauth_access.to_dict(), **kwargs)
        else:
            self.oauthsession = OAuth2Session(
                provider.client_id, redirect_uri=redirect_uri,
                scope=self.SCOPES, **kwargs)

    def _save_refresh_token(self, token):
        """
        Save tokens.

        Called by OAuthSession during refresh. Also used by fetch_token.
        """
        self.oauth_access.update(**token)

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
        return self.oauthsession.fetch_token(
            self.ACCESS_TOKEN_URL, authorization_response=request_uri,
            client_secret=self.provider.client_secret)

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
                # Do our own, since requests_oauthlib is broken.
                token = self.oauthsession.refresh_token(
                    self.REFRESH_TOKEN_URL,
                    refresh_token=self.oauth_access.refresh_token,
                    client_id=self.provider.client_id,
                    client_secret=self.provider.client_secret)
                self._save_refresh_token(token)
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


from main.fs.clouds.dropbox import DropboxAPIClient  # NOQA
from main.fs.clouds.onedrive import OnedriveAPIClient  # NOQA
from main.fs.clouds.box import BoxAPIClient  # NOQA
from main.fs.clouds.google import GDriveAPIClient  # NOQA

PROVIDERS = (
    DropboxAPIClient,
    OnedriveAPIClient,
    BoxAPIClient,
    GDriveAPIClient,
)
