import logging


LOGGER = logging.getLogger(__name__)


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


def get_client(provider, oauth_access=None, oauth_storage=None, **kwargs):
    for item in globals().values():
        if getattr(item, 'PROVIDER', None) == provider.provider:
            provider_cls = item
            break
    else:
        raise ValueError('Invalid provider')
    return provider_cls(provider, oauth_access=oauth_access,
                        oauth_storage=oauth_storage, **kwargs)
