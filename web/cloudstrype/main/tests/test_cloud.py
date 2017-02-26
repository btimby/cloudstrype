import httpretty

from hashlib import md5

from django.test import TestCase

from main.models import (
    User, File, OAuth2Provider, OAuth2AccessToken, OAuth2StorageToken,
    Chunk, ChunkStorage
)
from main.fs.cloud import (
    DropboxAPIClient, OnedriveAPIClient, BoxAPIClient, GDriveAPIClient
)

TEST_CHUNK_BODY = 'Test chunk body'


class OAuth2APIClientTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='foo@bar.org')
        self.provider = OAuth2Provider.objects.create(
            provider=self.PROVIDER,
            client_id='test-client_id',
            client_secret='test-client_secret')
        self.oauth_access = OAuth2AccessToken.objects.create(
            user=self.user,
            provider=self.provider, access_token='test-access_token',
            refresh_token='test-refresh_token')
        self.client = self.oauth_access.get_client()
        self.file = File.objects.create(path='/foo', user=self.user)
        self.chunk = Chunk.objects.create(md5=md5(b'foo').hexdigest())
        self.file.add_chunk(self.chunk)


class DropboxAPIClientTestCase(OAuth2APIClientTestCase):
    PROVIDER = OAuth2Provider.PROVIDER_DROPBOX

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
    PROVIDER = OAuth2Provider.PROVIDER_ONEDRIVE

    @httpretty.activate
    def test_download(self):
        # Onedrive requires the path in the URL, we use the chunk's uid as
        # path.
        httpretty.register_uri(
            httpretty.GET,
            OnedriveAPIClient.DOWNLOAD_URL[1].format(path=self.chunk.uid),
            body=TEST_CHUNK_BODY)

        self.assertEqual(TEST_CHUNK_BODY, self.client.download(self.chunk))

    @httpretty.activate
    def test_upload(self):
        httpretty.register_uri(
            httpretty.PUT,
            OnedriveAPIClient.DOWNLOAD_URL[1].format(path=self.chunk.uid),
            body='')

        self.client.upload(self.chunk, TEST_CHUNK_BODY)

    @httpretty.activate
    def test_delete(self):
        httpretty.register_uri(
            httpretty.DELETE,
            OnedriveAPIClient.DELETE_URL[1].format(path=self.chunk.uid),
            body=TEST_CHUNK_BODY)

        self.client.delete(self.chunk)

    def test_authorization_url(self):
        self.assertTrue(self.client.authorization_url())


class BoxAPIClientTestCase(OAuth2APIClientTestCase):
    PROVIDER = OAuth2Provider.PROVIDER_BOX

    def setUp(self):
        super().setUp()
        storage_token = OAuth2StorageToken.objects.create(
            user=self.user, token=self.oauth_access)
        ChunkStorage.objects.create(
            chunk=self.chunk, storage=storage_token,
            attrs={'file_id': 'abc123'})

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
    PROVIDER = OAuth2Provider.PROVIDER_GDRIVE

    def setUp(self):
        super().setUp()
        storage_token = OAuth2StorageToken.objects.create(
            user=self.user, token=self.oauth_access)
        ChunkStorage.objects.create(
            chunk=self.chunk, storage=storage_token,
            attrs={'file_id': 'abc123'})

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
            body='')

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
