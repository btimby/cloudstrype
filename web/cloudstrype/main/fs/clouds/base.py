import logging

from requests_oauthlib import OAuth2Session
from oauthlib.oauth2 import TokenExpiredError

from main.models import Chunk


LOGGER = logging.getLogger(__name__)


class HTTPError(Exception):
    def __init__(self, response):
        message = '%s: %s' % (response.status_code, response.text)
        super().__init__(message)


class BaseOAuth2APIClient(object):
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

    def __init__(self, provider, oauth_access=None, redirect_uri=None,
                 **kwargs):
        self.provider = provider
        self.oauth_access = oauth_access
        if self.oauth_access:
            # We already have a token, pass it along.
            self.oauthsession = OAuth2Session(
                token=self.oauth_access.to_dict(), **kwargs)
        else:
            # We have yet to obtain a token, so we have only the client ID etc.
            # needed to call `authorization_url()` and get a token.
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

    def _get_profile_fields(self, profile, *field_names):
        return list(map(lambda x: self._get_profile_field(profile, x),
                    field_names))

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
        profile.update(self.oauthsession.request(
            *self.USER_STORAGE_URL, **kwargs).json())

        return self._get_profile_fields(profile, 'uid', 'email', 'name',
                                        'size', 'used')

    def request(self, method, url, chunk, headers={}, **kwargs):
        """
        Perform HTTP request with OAuth.
        """
        tried_refresh = False
        while True:
            try:
                return self.oauthsession.request(method, url, headers=headers,
                                                 **kwargs)
            except TokenExpiredError:
                if tried_refresh:
                    break
                # Do our own, since requests_oauthlib is broken.
                token = self.oauthsession.refresh_token(
                    self.REFRESH_TOKEN_URL,
                    refresh_token=self.oauth_access.refresh_token,
                    client_id=self.provider.client_id,
                    client_secret=self.provider.client_secret)
                self._save_refresh_token(token)
                tried_refresh = True

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
