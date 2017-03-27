import httpretty

from hashlib import md5

from django.test import TestCase

from main.models import (
    User, File, BaseStorage, OAuth2Storage, OAuth2UserStorage, Chunk,
    ChunkStorage
)
from main.fs.clouds.dropbox import DropboxAPIClient
from main.fs.clouds.onedrive import OnedriveAPIClient
from main.fs.clouds.box import BoxAPIClient
from main.fs.clouds.google import GDriveAPIClient


TEST_CHUNK_BODY = b'Test chunk body'


class OAuth2APIClientTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='foo@bar.org')
        self.storage = OAuth2Storage.objects.create(
            client_id='test-client_id', client_secret='test-client_secret',
            provider=self.PROVIDER)
        self.oauth_access = OAuth2UserStorage.objects.create(
            user=self.user,
            storage=self.storage, access_token='test-access_token',
            refresh_token='test-refresh_token', attrs={'root.id': '0'})
        self.client = self.oauth_access.get_client()
        self.file = File.objects.create(path='/foo', user=self.user)
        self.chunk = Chunk.objects.create(md5=md5(b'foo').hexdigest())
        self.file.add_chunk(self.chunk)

    def _get_path(self):
        return '.cloudstrype/%s/%s' % (self.user.uid, self.chunk.uid)


class DropboxAPIClientTestCase(OAuth2APIClientTestCase):
    PROVIDER = BaseStorage.PROVIDER_DROPBOX

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
    PROVIDER = BaseStorage.PROVIDER_ONEDRIVE

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
    PROVIDER = BaseStorage.PROVIDER_BOX

    def setUp(self):
        super().setUp()
        ChunkStorage.objects.create(
            chunk=self.chunk, storage=self.oauth_access,
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
    PROVIDER = BaseStorage.PROVIDER_GDRIVE

    def setUp(self):
        super().setUp()
        ChunkStorage.objects.create(
            chunk=self.chunk, storage=self.oauth_access,
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
