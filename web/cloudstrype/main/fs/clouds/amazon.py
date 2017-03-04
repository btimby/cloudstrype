import logging

from main.fs.clouds.base import OAuth2APIClient
from main.models import OAuth2Provider


LOGGER = logging.getLogger(__name__)


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
