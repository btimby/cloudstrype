import logging


from main.fs.clouds.dropbox import DropboxAPIClient
from main.fs.clouds.onedrive import OnedriveAPIClient
from main.fs.clouds.box import BoxAPIClient
from main.fs.clouds.google import GDriveAPIClient


LOGGER = logging.getLogger(__name__)

PROVIDERS = (
    DropboxAPIClient,
    OnedriveAPIClient,
    BoxAPIClient,
    GDriveAPIClient,
)


def get_client(provider, oauth_access=None, **kwargs):
    for item in PROVIDERS:
        if getattr(item, 'PROVIDER', None) == provider.provider:
            provider_cls = item
            break
    else:
        raise ValueError('Invalid provider')
    return provider_cls(provider, oauth_access=oauth_access, **kwargs)
