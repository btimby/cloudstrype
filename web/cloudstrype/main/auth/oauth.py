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
        return self.oauthsession.authorization_url(
            self.provider.authorization_url)

    def fetch_token(self, request_uri):
        token = self.oauthsession.fetch_token(self.provider.access_token_url,
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
        profile = self.oauthsession.get(self.provider.user_profile_url).json()

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


class OnedriveClient(OAuth2Client):
    SCOPES = [
        'wl.basic', 'onedrive.readwrite', 'offline_access', 'wl.emails',
    ]
    PROVIDER = OAuth2Provider.PROVIDER_ONEDRIVE
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': ['emails', 'account'],
    }


class GDriveClient(OAuth2Client):
    SCOPES = [
        'profile', 'email', 'https://www.googleapis.com/auth/drive',
    ]
    PROVIDER = OAuth2Provider.PROVIDER_GDRIVE

    def authoriziation_url(self):
        return self.oauthsession.authorization_url(
            self.provider.authorization_url, access_type='offline')


class BoxClient(OAuth2Client):
    PROVIDER = OAuth2Provider.PROVIDER_BOX
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': 'login',
    }


class AmazonClient(OAuth2Client):
    PROVIDER = OAuth2Provider.PROVIDER_AMAZON


class SmartFileClient(OAuth2Client):
    PROVIDER = OAuth2Provider.PROVIDER_SMARTFILE
