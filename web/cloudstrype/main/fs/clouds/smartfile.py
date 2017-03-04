import logging

from main.fs.clouds.base import OAuth2APIClient
from main.models import OAuth2Provider


LOGGER = logging.getLogger(__name__)


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
