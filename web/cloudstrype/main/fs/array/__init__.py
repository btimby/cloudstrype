import logging

from os.path import join as pathjoin

import requests

from django.conf import settings

from main.models import Chunk, Storage


LOGGER = logging.getLogger(__name__)


def get_shared_arrays():
    arrays = []
    for name in settings.ARRAY_SHARED_NAMES:
        try:
            arrays.append(Storage.objects.get(type=Storage.TYPE_ARRAY,
                                              attrs__name=name))
        except Storage.DoesNotExist:
            LOGGER.warning('Invalid shared array name: %s', name)
            pass
    return arrays


class ArrayClient(object):
    TYPE = Storage.TYPE_ARRAY

    def __init__(self, storage):
        self.storage = storage
        self.user = storage.user
        self.name = storage.attrs['name']

    def request(self, method, path, headers={}, **kwargs):
        url = 'http://%s:%s/' % (settings.ARRAY_HOST, settings.ARRAY_PORT)
        url = pathjoin(url, path)
        return requests.request(method, url, headers=headers, **kwargs)

    def chunk_request(self, method, chunk, **kwargs):
        path = pathjoin(self.name, chunk.uid)
        return self.request(method, path, **kwargs)

    def download(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.chunk_request('GET', chunk, **kwargs)
        return r.content

    def upload(self, chunk, data, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.chunk_request('PUT', chunk, data=data, **kwargs)
        r.close()

    def delete(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.chunk_request('DELETE', chunk, **kwargs)
        r.close()

    def stats(self):
        return self.request('GET', '/api/stats/')
