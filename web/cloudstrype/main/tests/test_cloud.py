import httpretty

from django.test import TestCase

from main.models import (
    User, UserFile, Storage, Chunk, ChunkStorage,
)
from main.fs.clouds.dropbox import DropboxAPIClient
from main.fs.clouds.onedrive import OnedriveAPIClient
from main.fs.clouds.box import BoxAPIClient
from main.fs.clouds.google import GDriveAPIClient

TEST_CHUNK_BODY = b'Test chunk body'


class OAuth2APIClientTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(email='foo@bar.org')
        cls.storage = Storage.objects.create(type=cls.TYPE, user=cls.user)
        cls.storage.auth = {
            'access_token': 'test-access_token',
            'refresh_token': 'test-refresh_token',
        }
        cls.storage.attrs = {'root.id': 1}
        cls.file = UserFile.objects.create(path='/foo', user=cls.user)
        cls.chunk = Chunk.objects.create(size=1024, user=cls.user)
        cls.file.file.version.add_chunk(cls.chunk)

    def setUp(self):
        self.client = self.storage.get_client()

    def _get_path(self):
        return '.cloudstrype/%s/%s' % (self.user.uid, self.chunk.uid)


class DropboxAPIClientTestCase(OAuth2APIClientTestCase):
    TYPE = Storage.TYPE_DROPBOX

    @httpretty.activate
    def test_download(self):
        httpretty.register_uri(
            httpretty.POST, DropboxAPIClient.DOWNLOAD_URL[1],
            body=TEST_CHUNK_BODY)

        self.assertEqual(TEST_CHUNK_BODY, self.client.download(self.chunk))

    @httpretty.activate
    def test_upload(self):
        httpretty.register_uri(
            httpretty.POST, DropboxAPIClient.UPLOAD_URL[1],
            body='')

        self.client.upload(self.chunk, TEST_CHUNK_BODY)

    @httpretty.activate
    def test_delete(self):
        httpretty.register_uri(
            httpretty.POST, DropboxAPIClient.DELETE_URL[1],
            body=TEST_CHUNK_BODY)

        self.client.delete(self.chunk)

    def test_authorization_url(self):
        self.assertTrue(self.client.authorization_url())


class OnedriveAPIClientTestCase(OAuth2APIClientTestCase):
    TYPE = Storage.TYPE_ONEDRIVE

    @httpretty.activate
    def test_download(self):
        # Onedrive requires the path in the URL, we use the chunk's uid as
        # path.
        httpretty.register_uri(
            httpretty.GET,
            OnedriveAPIClient.DOWNLOAD_URL[1].format(path=self._get_path()),
            body=TEST_CHUNK_BODY)

        self.assertEqual(TEST_CHUNK_BODY, self.client.download(self.chunk))

    @httpretty.activate
    def test_upload(self):
        httpretty.register_uri(
            httpretty.PUT,
            OnedriveAPIClient.DOWNLOAD_URL[1].format(path=self._get_path()),
            body='')

        self.client.upload(self.chunk, TEST_CHUNK_BODY)

    @httpretty.activate
    def test_delete(self):
        httpretty.register_uri(
            httpretty.DELETE,
            OnedriveAPIClient.DELETE_URL[1].format(path=self._get_path()),
            body=TEST_CHUNK_BODY)

        self.client.delete(self.chunk)

    def test_authorization_url(self):
        self.assertTrue(self.client.authorization_url())


class BoxAPIClientTestCase(OAuth2APIClientTestCase):
    TYPE = Storage.TYPE_BOX

    def setUp(self):
        super().setUp()
        ChunkStorage.objects.create(
            chunk=self.chunk, storage=self.storage,
            attrs={'file.id': 'abc123'})

    @httpretty.activate
    def test_download(self):
        # Box requires the file id in the URL, the file_id is assigned by Box,
        # and therefore is stored in ChunkStorage.attrs.
        httpretty.register_uri(
            httpretty.GET,
            BoxAPIClient.DOWNLOAD_URL[1].format(file_id='abc123'),
            body=TEST_CHUNK_BODY)

        self.assertEqual(TEST_CHUNK_BODY, self.client.download(self.chunk))

    @httpretty.activate
    def test_upload(self):
        # Box requires the file id in the URL, the file_id is assigned by Box,
        # and therefore is stored in ChunkStorage.attrs.
        httpretty.register_uri(
            httpretty.POST,
            BoxAPIClient.UPLOAD_URL[1].format(file_id='abc123'),
            body='{"entries": [{"id":1}]}', content_type='application/json')

        self.client.upload(self.chunk, TEST_CHUNK_BODY)

    @httpretty.activate
    def test_delete(self):
        # Box requires the file id in the URL, the file_id is assigned by Box,
        # and therefore is stored in ChunkStorage.attrs.
        httpretty.register_uri(
            httpretty.DELETE,
            BoxAPIClient.DELETE_URL[1].format(file_id='abc123'),
            body=TEST_CHUNK_BODY)

        self.client.delete(self.chunk)

    def test_authorization_url(self):
        self.assertTrue(self.client.authorization_url())


class GDriveAPIClientTestCase(OAuth2APIClientTestCase):
    TYPE = Storage.TYPE_GOOGLE

    def setUp(self):
        super().setUp()
        ChunkStorage.objects.create(
            chunk=self.chunk, storage=self.storage,
            attrs={'file.id': 'abc123'})

    @httpretty.activate
    def test_download(self):
        # GDrive requires the file id in the URL, the file_id is assigned by
        # Google, and therefore is stored in ChunkStorage.attrs.
        httpretty.register_uri(
            httpretty.GET,
            GDriveAPIClient.DOWNLOAD_URL[1].format(file_id='abc123'),
            body=TEST_CHUNK_BODY)

        self.assertEqual(TEST_CHUNK_BODY, self.client.download(self.chunk))

    @httpretty.activate
    def test_upload(self):
        # GDrive requires the file id in the URL, the file_id is assigned by
        # Google, and therefore is stored in ChunkStorage.attrs.
        httpretty.register_uri(
            httpretty.POST,
            GDriveAPIClient.UPLOAD_URL[1].format(file_id='abc123'),
            body='{"id":1234}')

        self.client.upload(self.chunk, TEST_CHUNK_BODY)

    @httpretty.activate
    def test_delete(self):
        # GDrive requires the file id in the URL, the file_id is assigned by
        # Google, and therefore is stored in ChunkStorage.attrs.
        httpretty.register_uri(
            httpretty.DELETE,
            GDriveAPIClient.DELETE_URL[1].format(file_id='abc123'),
            body=TEST_CHUNK_BODY)

        self.client.delete(self.chunk)

    def test_authorization_url(self):
        self.assertTrue(self.client.authorization_url())
