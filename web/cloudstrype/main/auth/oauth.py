from datetime import datetime, timezone, timedelta
from inspect import isclass

from requests_oauthlib import OAuth2Session

from main.models import OAuth2Provider


class OAuth2Client(object):
    SCOPES = []
    PROFILE_FIELDS = {
        'uid': 'uid',
        'email': 'email',
    }
    PROVIDER = None

    @classmethod
    def get_client(cls, provider, redirect_uri, **kwargs):
        provider_cls = cls
        for item in globals().values():
            if isclass(item) and issubclass(item, cls) and \
               getattr(item, 'PROVIDER', None) == provider.provider:
                   provider_cls = item
                   break
        else:
            raise ValueError('Invalid provider')
        return provider_cls(provider, redirect_uri, **kwargs)

    def __init__(self, provider, redirect_uri, **kwargs):
        self.provider = provider
        self.oauthsession = OAuth2Session(
            provider.client_id, redirect_uri=redirect_uri, scope=self.SCOPES,
            **kwargs)

    def authorization_url(self):
        return self.oauthsession.authorization_url(self.AUTHORIZATION_URL)

    def fetch_token(self, request_uri):
        token = self.oauthsession.fetch_token(self.ACCESS_TOKEN_URL,
            authorization_response=request_uri,
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

    def get_profile(self):
        profile = self.oauthsession.get(self.USER_PROFILE_URL).json()

        def _get(field_name):
            if isinstance(field_name, str):
                return profile.get(field_name)
            else:
                value, field_name = profile, field_name[:]
                while field_name:
                    value = value.get(field_name.pop(0))
                return value

        uid_field = self.PROFILE_FIELDS['uid']
        email_field = self.PROFILE_FIELDS['email']
        return _get(uid_field), _get(email_field)


class DropboxClient(OAuth2Client):
    PROVIDER = OAuth2Provider.PROVIDER_DROPBOX

    AUTHORIZATION_URL = 'https://www.dropbox.com/1/oauth2/authorize'
    ACCESS_TOKEN_URL = 'https://api.dropbox.com/1/oauth2/token'
    REFRESH_TOKEN_URL = None
    USER_PROFILE_URL = 'https://api.dropbox.com/1/account/info'


class OnedriveClient(OAuth2Client):
    SCOPES = [
        'wl.basic', 'onedrive.readwrite', 'offline_access', 'wl.emails',
    ]
    PROVIDER = OAuth2Provider.PROVIDER_ONEDRIVE
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': ['emails', 'account'],
    }

    AUTHORIZATION_URL = 'https://login.live.com/oauth20_authorize.srf'
    ACCESS_TOKEN_URL = 'https://login.live.com/oauth20_token.srf'
    REFRESH_TOKEN_URL = 'https://login.live.com/oauth20_token.srf'
    USER_PROFILE_URL = 'https://apis.live.net/v5.0/me'


class GDriveClient(OAuth2Client):
    SCOPES = [
        'profile', 'email', 'https://www.googleapis.com/auth/drive',
    ]
    PROVIDER = OAuth2Provider.PROVIDER_GDRIVE

    AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    ACCESS_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
    REFRESH_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
    USER_PROFILE_URL = 'https://www.googleapis.com/oauth2/v1/userinfo'

    def authoriziation_url(self):
        return self.oauthsession.authorization_url(
            self.AUTHORIZATION_URL, access_type='offline')


class BoxClient(OAuth2Client):
    PROVIDER = OAuth2Provider.PROVIDER_BOX
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': 'login',
    }

    AUTHORIZATION_URL = 'https://account.box.com/api/oauth2/authorize'
    ACCESS_TOKEN_URL = 'https://api.box.com/oauth2/token'
    REFRESH_TOKEN_URL = 'https://api.box.com/oauth2/token'
    USER_PROFILE_URL = 'https://api.box.com/2.0/users/me'


class AmazonClient(OAuth2Client):
    PROVIDER = OAuth2Provider.PROVIDER_AMAZON

    AUTHORIZATION_URL = ''
    ACCESS_TOKEN_URL = ''
    REFRESH_TOKEN_URL = ''
    USER_PROFILE_URL = ''


class SmartFileClient(OAuth2Client):
    PROVIDER = OAuth2Provider.PROVIDER_SMARTFILE

    AUTHORIZATION_URL = ''
    ACCESS_TOKEN_URL = ''
    REFRESH_TOKEN_URL = ''
    USER_PROFILE_URL = ''
