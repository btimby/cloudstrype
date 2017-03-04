import json
import logging

from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase

from main.fs import Chunk
from main.fs.clouds.base import OAuth2APIClient
from main.models import OAuth2Provider


LOGGER = logging.getLogger(__name__)


class GDriveAPIClient(OAuth2APIClient):
    """
    OAuth2 API client for Google Drive.

    Unholy fuck-shits is all I have to say.
    """
    PROVIDER = OAuth2Provider.PROVIDER_GDRIVE
    SCOPES = [
        'profile', 'email', 'https://www.googleapis.com/auth/drive',
    ]
    PROFILE_FIELDS = {
        'uid': 'id',
        'email': 'email',
        'name': 'name',
        'size': 'quotaBytesTotal',
        'used': 'quotaBytesUsed',
    }

    AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
    ACCESS_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'
    REFRESH_TOKEN_URL = 'https://www.googleapis.com/oauth2/v4/token'

    USER_PROFILE_URL = ('get', 'https://www.googleapis.com/oauth2/v1/userinfo')
    USER_STORAGE_URL = ('get', 'https://www.googleapis.com/drive/v2/about')

    DOWNLOAD_URL = \
        ('GET',
         'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media')
    UPLOAD_URL = \
        ('POST', 'https://www.googleapis.com/upload/drive/v2/files')
    DELETE_URL = \
        ('DELETE', 'https://www.googleapis.com/drive/v2/files/{file_id}')

    CREATE_URL = 'https://www.googleapis.com/drive/v2/files'

    def download(self, chunk, **kwargs):
        "Overidden to add file_id to URL."
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        method, url = self.DOWNLOAD_URL
        url = url.format(file_id=chunk_storage.attrs['file.id'])
        r = self.request(method, url, chunk, **kwargs)
        return r.content

    def upload(self, chunk, data, **kwargs):
        """
        Overridden to perform uploads.

        Google is the most problematic of the clouds. Their API is pretty
        horrible to work with for the following reasons:

        They are _very_ particular in the formatting of requests, and they
        require atypical formatting, so not fun.

        Something that works one day will stop working the next. In particular
        what MIME types they accept. In fact most of my problems have been
        related to MIME types.
        """
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        try:
            parent_id = self.oauth_storage.attrs.get('root.id')
        except ValueError:
            parent_id = None
        attrs = {
            'mimeType': 'application/vnd.google-apps.unknown',
            'title': chunk.uid,
            'description': 'Cloudstrype chunk',
        }
        if parent_id:
            attrs['parents'] = [{'id': parent_id}]

        # Google wants multipart/related, which requests does not do by default
        # so we craft the multipart request body using MIME tools.
        related = MIMEMultipart('related')
        jsonpart = MIMEBase('application', 'json', charset='utf-8')
        jsonpart.set_payload(json.dumps(attrs))
        related.attach(jsonpart)
        chunkpart = MIMEBase('text', 'plain')
        chunkpart.set_payload(data)
        related.attach(chunkpart)

        # Get the body, discarding the headers, then get the headers as a dict
        # allowing requests to handle the headers.
        body = related.as_string().split('\n\n', 1)[1]
        headers = dict(related.items())

        method, url = self.UPLOAD_URL
        url += '?uploadType=multipart'
        r = self.request(method, url, chunk, data=body, headers=headers,
                         **kwargs)

        if not 199 < r.status_code < 300:
            raise Exception('%s: "%s"' % (r.status_code, r.text))
        attrs = r.json()
        if 'id' not in attrs:
            LOGGER.error('key "id" not in response "%s"', attrs)
            raise KeyError('id')
        # Store the file ID provided by Google into the attribute store of
        # ChunkStorage
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        chunk_storage.attrs = {'file.id': attrs['id']}
        chunk_storage.save()
        r.close()

    def delete(self, chunk, **kwargs):
        """
        Overidden to add file_id to URL.

        When uploading we store the resulting file ID in a property of the
        ChunkStorage instance. This allows us to download the file without
        discovering it's ID from it's path.
        """
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        chunk_storage = chunk.storage.get(
            storage__token__provider__provider=self.PROVIDER)
        method, url = self.DELETE_URL
        url = url.format(file_id=chunk_storage.attrs['file.id'])
        r = self.request(method, url, chunk, **kwargs)
        r.close()

    def authorization_url(self):
        """
        Overidden to add access_type=offline.

        Offline access results in a refresh token being issued. Google refresh
        tokens are long-lived, so we don't rotate it when we perform a refresh.
        """
        return self.oauthsession.authorization_url(
            self.AUTHORIZATION_URL, access_type='offline')

    def initialize(self):
        """
        Overidden to create a storage location.

        We create a storage directory for Cloudstrype, and store it's id so we
        can upload to it later.

        Unlike the Box API (which also requires this nonsense) Google does not
        report a conflict for items with the SAME NAME. I guess I am too
        stoopid to understand why I would want two things with the same name.
        Anyway, we have to do a round-trip to check existence first, otherwise
        we will create duplicates, which would be even stoopider.

        So, this means we make *FOUR* api calls to initialze our directory.
        """
        # Omit parent to put file in root. Provide first's ID to place second
        # inside it.
        parent_id, kwargs = None, {
            'headers': {'Content-Type': 'application/json'}
        }
        for name in ('.cloudstrype', self.oauth_access.user.uid):
            # Hey Google, fuck you for making me do this!
            query = [
                "title='%s'" % name,
            ]
            if parent_id:
                query.append("'%s' in parents" % parent_id)
            params = {
                'q': ' and '.join(query),
            }
            r = self.oauthsession.get(self.CREATE_URL, params=params)
            if r.status_code == 200:
                parent_id = r.json()['items'][0]['id']
                continue

            # OK, with that extra round-trip out of the way, let's create the
            # missing directory.
            data = {
                'mimeType': 'application/vnd.google-apps.folder',
                'title': name,
                'description': 'Cloudstrype storage',
            }
            if parent_id:
                data['parents'] = [{'id': parent_id}]
            # The body of the request should be our JSON object as string.
            kwargs['data'] = json.dumps(data)
            # Create the directory:
            r = self.oauthsession.post(self.CREATE_URL, **kwargs)
            parent_id = r.json()['id']
        self.oauth_storage.attrs = {'root.id': parent_id}
        self.oauth_storage.save()
