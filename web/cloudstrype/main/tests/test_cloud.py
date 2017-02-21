import os
import asyncio

from io import BytesIO
from unittest import skipIf

from django.test import TestCase

from main.fs.async import Chunk
from main.fs.async.cloud.dropbox import DropboxProvider
from main.fs.async.cloud.onedrive import OnedriveProvider
from main.fs.async.cloud.box import BoxProvider


TEST_FILE = b'This file is used for unit testing. See cloudstrype.io'


class AsyncTestCase(TestCase):
    """
    Convenience class that runs coroutines.
    """

    def setUp(self):
        self.loop = asyncio.get_event_loop()

    def _execute(self, coroutine):
        return self.loop.run_until_complete(asyncio.ensure_future(coroutine))


class ProviderTests(object):
    """
    Test cases to run for all providers.
    """

    def test_provider(self):
        chunk = Chunk({}, TEST_FILE, 'cloudstrype-unittest')
        self._execute(
            self.client.upload(chunk))

        chunk = Chunk(chunk.clouds, None, 'cloudstrype-unittest')
        self._execute(
            self.client.download(chunk))
        self.assertEqual(TEST_FILE, chunk.data)

        self._execute(
            self.client.delete(chunk))


@skipIf('DROPBOX_OAUTH' not in os.environ, 'No OAuth key in DROPBOX_OAUTH')
class DropboxTestCase(AsyncTestCase, ProviderTests):
    def setUp(self):
        super().setUp()
        self.client = DropboxProvider(1, {'token': os.environ['DROPBOX_OAUTH']})


@skipIf('ONEDRIVE_OAUTH' not in os.environ, 'No OAuth key in ONEDRIVE_OAUTH')
class OnedriveTestCase(AsyncTestCase, ProviderTests):
    def setUp(self):
        super().setUp()
        self.client = OnedriveProvider(1, {'token': os.environ['ONEDRIVE_OAUTH']})


@skipIf('BOX_OAUTH' not in os.environ, 'No OAuth key in BOX_OAUTH')
class BoxTestCase(AsyncTestCase, ProviderTests):
    def setUp(self):
        super().setUp()
        self.client = BoxProvider(1, {'token': os.environ['BOX_OAUTH']})
