from os.path import basename

from django.db.models import Sum
from django.http import StreamingHttpResponse

from rest_framework import (
    serializers, permissions, views, generics, response, exceptions, parsers
)

from main.fs import MulticloudFilesystem
from main.fs.errors import DirectoryNotFoundError, FileNotFoundError
from main.models import (
    User, OAuth2Provider, OAuth2StorageToken, Directory, File,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('uid', 'email', 'full_name', 'first_name', 'last_name')


class MeView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    template_name = 'api/me.html'

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class OAuth2ProviderSerializer(serializers.ModelSerializer):

    size = serializers.SerializerMethodField()
    used = serializers.SerializerMethodField()

    class Meta:
        model = OAuth2Provider
        fields = ('name', 'size', 'used')

    def get_size(self, obj):
        return OAuth2StorageToken.objects.filter(
            token__provider=obj).aggregate(Sum('size'))['size__sum'] or 0

    def get_used(self, obj):
        return OAuth2StorageToken.objects.filter(
            token__provider=obj).aggregate(Sum('used'))['used__sum'] or 0


class PublicCloudListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    queryset = OAuth2StorageToken.objects.all()
    serializer_class = OAuth2ProviderSerializer

    def get_queryset(self):
        return OAuth2Provider.objects.all()


class OAuth2StorageTokenSerializer(serializers.ModelSerializer):

    name = serializers.CharField(source='token.provider.name')

    class Meta:
        model = OAuth2StorageToken
        fields = ('name', 'size', 'used')


class CloudListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = OAuth2StorageToken.objects.all()
    serializer_class = OAuth2StorageTokenSerializer

    def get_queryset(self):
        queryset = OAuth2StorageToken.objects.filter(
            user=self.request.user)
        return (o for o in queryset if o.token.provider.is_storage)


class DirectorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Directory
        fields = ('uid', 'name', 'path', 'tags', 'attrs')


class FileSerializer(serializers.ModelSerializer):
    class Meta:
        model = File
        fields = ('uid', 'name', 'path', 'size', 'md5', 'sha1', 'created',
                  'tags', 'attrs')


class DirectoryListingSerializer(serializers.Serializer):
    info = DirectorySerializer()
    dirs = DirectorySerializer(many=True)
    files = FileSerializer(many=True)


class FSView(views.APIView):
    def get_fs(self):
        return MulticloudFilesystem(self.request.user)


class DirectoryUidView(FSView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, uid, format=None):
        try:
            dir = Directory.objects.get(uid=uid, user=request.user)
        except Directory.DoesNotExist:
            raise exceptions.NotFound(uid)
        dir, dirs, files = self.get_fs().listdir(dir.path, dir=dir)
        return response.Response(DirectoryListingSerializer({
            'info': dir, 'dirs': dirs, 'files': files
        }).data)

    def delete(self, request, uid, format=None):
        try:
            dir = Directory.objects.get(uid=uid, user=request.user)
        except Directory.DoesNotExist:
            raise exceptions.NotFound(uid)
        try:
            return response.Response(self.get_fs().rmdir(dir.path))
        except DirectoryNotFoundError:
            raise exceptions.NotFound()


class DirectoryPathView(FSView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, path, format=None):
        try:
            dir, dirs, files = self.get_fs().listdir(path)
        except DirectoryNotFoundError:
            if path != '/':
                raise exceptions.NotFound()
            dir, dirs, files = Directory(path='/'), [], []
        return response.Response(DirectoryListingSerializer({
            'info': dir, 'dirs': dirs, 'files': files
        }).data)

    def post(self, request, path, format=None):
        return response.Response(
            DirectorySerializer(self.get_fs().mkdir(path)).data)

    def delete(self, request, path, format=None):
        if path == '/':
            raise exceptions.ValidationError('Cannot delete root')
        try:
            return response.Response(self.get_fs().rmdir(path))
        except DirectoryNotFoundError:
            raise exceptions.NotFound()


class FileUidView(FSView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, uid, format=None):
        try:
            file = File.objects.get(uid=uid, user=self.user)
        except File.DoesNotExist:
            raise exceptions.NotFound(uid)
        return response.Response(
            FileSerializer(self.get_fs().info(file.path, file=file)))


class FilePathView(FSView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, path, format=None):
        try:
            return response.Response(FileSerializer(self.get_fs().info(path)))
        except FileNotFoundError:
            raise exceptions.NotFound(path)


class UrlUidFilenameUploadParser(parsers.FileUploadParser):
    """
    Override `get_filename()` to support our URL path structure.

    The default Parser expects a named arg filename in the URL pattern. However
    to be consistent, we override it so that we can use the path or uid in the
    url.
    """

    def get_filename(self, stream, media_type, parser_context):
        try:
            request = parser_context['request']
            id = parser_context['args'][0]
        except (KeyError, IndexError):
            return
        if not id.startswith('/'):
            try:
                return File.objects.get(uid=id, user=request.user).name
            except File.DoesNotExist:
                return
        return basename(id)


class DataUidView(FSView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)

    def get(self, request, uid, format=None):
        try:
            file = File.objects.get(uid=uid)
        except File.DoesNotExist:
            raise exceptions.NotFound(uid)
        return StreamingHttpResponse(self.get_fs().download(file.path))

    def post(self, request, uid, format=None):
        try:
            file = File.objects.get(uid=uid, user=request.user)
        except File.DoesNotExist:
            raise exceptions.NotFound(uid)
        file = self.get_fs().upload(file.path, f=request.data['file'])
        return response.Response(FileSerializer(file).data)


class DataPathView(FSView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)

    def get(self, request, path, format=None):
        try:
            return StreamingHttpResponse(self.get_fs().download(path))
        except FileNotFoundError:
            raise exceptions.NotFound(path)

    def post(self, request, path, format=None):
        file = self.get_fs().upload(path, f=request.data['file'])
        return response.Response(FileSerializer(file).data)
