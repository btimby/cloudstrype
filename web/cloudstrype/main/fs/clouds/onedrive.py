import logging

from main.fs.clouds.base import OAuth2APIClient
from main.models import OAuth2Provider


LOGGER = logging.getLogger(__name__)


class OnedriveAPIClient(OAuth2APIClient):
    """
    OAuth2 API client for OneDrive.

    I feel icky saying this but OneDrive's API is the nicest to deal with; even
    better than Dropbox. It works and is sane, I have yet to have problems
    with it.

    So, this is the second Microsoft product (right after SQL Server 2000) that
    I like! Kudos M$.
    """

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
