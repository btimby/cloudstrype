import os
import logging

from main.fs.clouds.dropbox import DropboxAPIClient
from main.fs.clouds.onedrive import OnedriveAPIClient
from main.fs.clouds.box import BoxAPIClient
from main.fs.clouds.google import GDriveAPIClient
from main.fs.array import ArrayClient


LOGGER = logging.getLogger(__name__)

CLIENTS = (
    DropboxAPIClient,
    OnedriveAPIClient,
    BoxAPIClient,
    GDriveAPIClient,
    ArrayClient,
)


def get_client(type, storage=None, **kwargs):
    try:
        slug = Storage.TYPE_SLUGS[type]
    except KeyError as e:
        raise ValueError('Invalid type %s' % e.args[0])
    for item in CLIENTS:
        if getattr(item, 'TYPE', None) == type:
            client_class = item
            break
    else:
        raise NotImplementedError('No client for type %s' % slug)
    if type == Storage.TYPE_ARRAY:
        return client_class(storage)
    try:
        client_id = os.environ['%s_CLIENT_ID' % slug.upper()]
        client_secret = os.environ['%s_CLIENT_SECRET' % slug.upper()]
    except KeyError as e:
        raise ImproperlyConfigured('Missing %s environment variable' % \
                                   e.args[0])
    if storage:
        kwargs.setdefault('user', storage.user)
        kwargs.setdefault('token', storage.auth)
        kwargs.setdefault('token_callback', storage.auth_update)
    return client_class(client_id, client_secret, storage=storage, **kwargs)


from main.models import Storage