import logging

from os.path import join as pathjoin

import requests

from django.conf import settings

from main.models import Chunk, Storage


LOGGER = logging.getLogger(__name__)


class ArrayClient(object):
    TYPE = Storage.TYPE_ARRAY

    def __init__(self, storage):
        self.storage = storage
        self.user = storage.user
        self.name = storage.name

    def request(self, method, chunk, headers={}, **kwargs):
        url = pathjoin(settings.ARRAY_SERVER_URL, self.name, chunk.id)
        return requests.request(method, url, headers=headers, **kwargs)

    def download(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request('GET', chunk, **kwargs)
        return r.content

    def upload(self, chunk, data, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request('PUT', chunk, data=data, **kwargs)
        r.close()

    def delete(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request('DELETE', chunk, **kwargs)
        r.close()
