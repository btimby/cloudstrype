from inspect import isclass

from requests_oauthlib import OAuth2Session

from .. import Chunk
from main.models import OAuth2Provider


class OAuth2APIClient(object):
    """
    OAuth API client base class.
    """

    @classmethod
    def get_client(cls, oauth_access, **kwargs):
        provider_cls = cls
        for item in globals().values():
            if isclass(item) and issubclass(item, cls) and \
               getattr(item, 'PROVIDER', None) == provider.provider:
                   provider_cls = item
                   break
        else:
            raise ValueError('Invalid provider')
        return provider_cls(oauth_access, **kwargs)

    def __init__(self, oauth_access, **kwargs):
        self.oauth_access = oauth_access
        self.provider = oauth_access.provider
        token = {
            'access_token': self.oauth_access.access_token,
            'refresh_token': self.oauth_access.refresh_token
        }
        self.oauthsession = OAuth2Session(
            token=token, auto_refresh_url=self.provider.token_refresh_url,
            token_updater=self._refresh_token_callback, **kwargs)

    def _refresh_token_callback(self, token):
        "Called by OAuth2Session when a token is refreshed."
        self.oauth_access.access_token = token
        self.oauth_access.save()

    def request(self, method, url, chunk, headers={}, **kwargs):
        """
        Perform HTTP request for OAuth.
        """
        headers['Authorization'] = 'Bearer %s' % self.token
        return super().request(method, url, headers=headers, **kwargs)

    def download(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(*self.DOWNLOAD_URL, chunk)
        chunk.data = r.read()

    def upload(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(*self.UPLOAD_URL, chunk, data=chunk.data)
        r.close()

    def delete(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(*self.DELETE_URL, chunk)
        r.close()


class DropboxAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_DROPBOX

    DOWNLOAD_URL = ('post', 'https://content.dropboxapi.com/2/files/download')
    UPLOAD_URL = ('post', 'https://content.dropboxapi.com/2/files/upload')
    DELETE_URL = ('post', 'https://api.dropboxapi.com/2/files/delete')

    def request(self, method, url, chunk, headers={}, **kwargs):
        headers['Dropbox-API-Arg'] = json.dumps({'path': '/%s' % chunk.id})
        return super().request(method, url, chunk, headers=headers, **kwargs)

    def upload(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        headers = {
            'Content-Type': 'application/octet-stream',
        }
        r = self.request(*self.UPLOAD_URL, chunk, headers=headers,
                         data=chunk.data)
        r.close()

    def download(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        r = self.request(*self.DOWNLOAD_URL, chunk)
        chunk.data = r.read()

    def delete(self, chunk, **kwargs):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        headers = {
            'Content-Type': 'application/json'
        }
        r = super().request(*self.DELETE_URL, chunk, headers=headers,
                            data=json.dumps({'path': '/%s' % chunk.id}))
        r.close()


class OnedriveAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_ONEDRIVE

    DOWNLOAD_URL = \
        ('get', 'https://api.onedrive.com/v1.0/drive/root:/{path}:/content')
    UPLOAD_URL = \
        ('put', 'https://api.onedrive.com/v1.0/drive/root:/{path}:/content')
    DELETE_URL = \
        ('delete', 'https://api.onedrive.com/v1.0/drive/root:/{path}')

    def request(self, method, url, chunk, headers={}, **kwargs):
        url = url.format(path=chunk.id)
        return super().request(method, url, chunk, headers=headers, **kwargs)


class BoxAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_BOX

    DOWNLOAD_URL = ('get', 'https://api.box.com/2.0/files/{file_id}/content')
    UPLOAD_URL = ('post', 'https://upload.box.com/api/2.0/files/content')
    DELETE_URL = ('delete', 'https://api.box.com/2.0/files/{file_id}')

    def request(self, method, url, chunk, headers={}, **kwargs):
        url = url.format(file_id=chunk.clouds[self.id]['file_id'])
        return super().request(method, url, chunk, headers=headers, **kwargs)

    def upload(self, chunk):
        assert isinstance(chunk, Chunk), 'must be chunk instance'
        data = {
            'attributes': json.dumps({'name': chunk.id, 'parent': {'id': 0}}),
            'file': BytesIO(chunk.data),
        }
        tries = 0
        while True:
            tries += 1
            try:
                r = self.request(*self.UPLOAD_URL, chunk, data=data)
                break
            except HTTPError as e:
                if tries < 3 and e.response.status == 409:
                    # 409 means a file with that name exists...
                    error = e.response.json()
                    # Grab the id of the existing file...
                    chunk.clouds.setdefault(self.id, {})['file_id'] = \
                        error['context_info']['conflicts']['id']
                    # And delete it...
                    self.delete(chunk)
                    # Then try again.
                    continue
                raise
        attrs = r.json()
        chunk.clouds[self.id] = {'file_id': attrs['entries'][0]['id']}
        r.close()


class GDriveAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_GDRIVE

    DOWNLOAD_URL = \
        ('GET', 'https://www.googleapis.com/drive/v3/files/{file_id}?alt=media')
    UPLOAD_URL = \
        ('POST', 'https://www.googleapis.com/upload/drive/v2/files')
    DELETE_URL = \
        ('DELETE', 'https://www.googleapis.com/drive/v2/files/{file_id}')


class SmartFileAPIClient(OAuth2APIClient):
    PROVIDER = OAuth2Provider.PROVIDER_SMARTFILE

    DOWNLOAD_URL = ('get', 'https://app.smartfile.com/api/2/path/data/{path}')
    UPLOAD_URL = ('post', 'https://app.smartfile.com/api/2/path/data/{dir}')
    DELETE_URL = ('delete', 'https://app.smartfile.com/api/2/path/data/{path}')

    def request(self, method, url, chunk, headers={}, **kwargs):
        url = url.format(path=chunk.id, dir='')
        return super().request(method, url, chunk, headers=headers, **kwargs)

    def upload(self, chunk):


class S3APIClient(object):
    PROVIDER = OAuth2Provider.PROVIDER_AMAZON
