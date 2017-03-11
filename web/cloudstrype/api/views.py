"""
API views.

This file contains the serializers views and supporting code that produces the
API.
"""

from os.path import basename

from django.db.models import Sum
from django.http import StreamingHttpResponse

from rest_framework import (
    serializers, permissions, views, generics, response, exceptions, parsers,
    mixins
)

from main.fs import MulticloudFilesystem
from main.fs.errors import DirectoryNotFoundError, FileNotFoundError
from main.models import (
    User, OAuth2Provider, OAuth2StorageToken, Directory, File, ChunkStorage,
    Option
)


class OAuth2ProviderSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud.

    Provides statistics for a supported cloud.
    """

    size = serializers.SerializerMethodField()
    used = serializers.SerializerMethodField()
    chunks = serializers.SerializerMethodField()

    class Meta:
        model = OAuth2Provider
        fields = ('name', 'size', 'used', 'chunks')

    def get_size(self, obj):
        return OAuth2StorageToken.objects.filter(
            token__provider=obj).aggregate(Sum('size'))['size__sum'] or 0

    def get_used(self, obj):
        return OAuth2StorageToken.objects.filter(
            token__provider=obj).aggregate(Sum('used'))['used__sum'] or 0

    def get_chunks(self, obj):
        return ChunkStorage.objects.filter(
            storage__token__provider=obj).count()


class PublicCloudListView(generics.ListAPIView):
    """
    List Clouds.

    Provides system-wide information/stats about a supported clouds. Used to
    generate menus and graphs on public site.
    """

    permission_classes = [permissions.AllowAny]
    queryset = OAuth2StorageToken.objects.all()
    serializer_class = OAuth2ProviderSerializer

    def get_queryset(self):
        return OAuth2Provider.objects.all().order_by('provider')


class UserSerializer(serializers.ModelSerializer):
    """
    Serialize a User.

    Provides details for a user.
    """

    class Meta:
        model = User
        fields = ('uid', 'email', 'full_name', 'first_name', 'last_name')


class MeView(generics.RetrieveAPIView):
    """
    Ubiquitous "ME" view.

    Displays current user.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    template_name = 'api/me.html'

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class OptionsSerializer(serializers.ModelSerializer):
    """
    Serialize a User's Options.

    Provide user's option list.
    """

    class Meta:
        model = Option
        fields = ('raid_level', 'raid_replicas')


class OptionsView(mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                  generics.GenericAPIView):
    """
    Option view.

    Allows user to view/set their account options.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OptionsSerializer
    template_name = 'api/me.html'

    def get_object(self):
        try:
            return self.request.user.options
        except Option.DoesNotExist:
            pass

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)


class OAuth2StorageTokenSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud instance.

    Provides statistics for a cloud account.
    """

    name = serializers.CharField(source='token.provider.name')
    chunks = serializers.SerializerMethodField()

    class Meta:
        model = OAuth2StorageToken
        fields = ('name', 'size', 'used', 'chunks')

    def get_chunks(self, obj):
        return obj.chunks.all().count()


class CloudListView(generics.ListAPIView):
    """
    List Cloud accounts.

    Provides a single user's information/stats about a single cloud account.
    Used to manage their cloud connections.
    """

    permission_classes = [permissions.IsAuthenticated]
    queryset = OAuth2StorageToken.objects.all()
    serializer_class = OAuth2StorageTokenSerializer

    def get_queryset(self):
        queryset = OAuth2StorageToken.objects.filter(
            user=self.request.user).order_by('token__provider__provider')
        return (o for o in queryset if o.token.provider.is_storage)


class DirectorySerializer(serializers.ModelSerializer):
    """
    Serialize a Directory.

    Provides details about a directory.
    """

    class Meta:
        model = Directory
        fields = ('uid', 'name', 'path', 'created', 'tags', 'attrs')


class FileSerializer(serializers.ModelSerializer):
    """
    Serialize a File.

    Provides details about a File.
    """

    chunks = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = ('uid', 'name', 'extension', 'path', 'size', 'chunks', 'md5',
                  'sha1', 'mime', 'created', 'raid_level', 'tags', 'attrs')

    def get_chunks(self, obj):
        return obj.chunks.all().count()


class DirectoryListingSerializer(serializers.Serializer):
    """
    Serialize a Directory and it's contents.

    Provides details about a Directory as well as a listing of Directories and
    files contained within it.
    """

    info = DirectorySerializer()
    dirs = DirectorySerializer(many=True)
    files = FileSerializer(many=True)


class BaseFSView(views.APIView):
    """
    Filesystem base class.

    Provides functionality common to all FS views.
    """

    def get_fs(self):
        return MulticloudFilesystem(self.request.user)


class DirectoryUidView(BaseFSView):
    """
    Directory detail view.

    Provides Directory listing for a directory identified by it's uid.
    """

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
            raise exceptions.NotFound(uid)


class DirectoryPathView(BaseFSView):
    """
    Directory detail view.

    Provides Directory listing for a directory identified by it's path.
    """

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
            raise exceptions.NotFound(path)


class FileUidView(BaseFSView):
    """
    File detail view.

    Provides File information for a file identified by it's uid.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, uid, format=None):
        try:
            file = File.objects.get(uid=uid, user=request.user)
        except File.DoesNotExist:
            raise exceptions.NotFound(uid)
        return response.Response(
            FileSerializer(self.get_fs().info(file.path, file=file)).data)

    def delete(self, request, uid, format=None):
        try:
            file = File.objects.get(uid=uid, user=request.user)
        except File.DoesNotExist:
            raise exceptions.NotFound(uid)
        return response.Response(self.get_fs().delete(file.path))


class FilePathView(BaseFSView):
    """
    File detail view.

    Provides File information for a file identified by it's path.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, path, format=None):
        try:
            return response.Response(
                FileSerializer(self.get_fs().info(path)).data)
        except FileNotFoundError:
            raise exceptions.NotFound(path)

    def delete(self, request, path, format=None):
        try:
            return response.Response(self.get_fs().delete(path))
        except FileNotFoundError:
            raise exceptions.NotFound(path)


class UrlUidFilenameUploadParser(parsers.FileUploadParser):
    """
    Override `get_filename()` to support our URL path structure.

    Allows uploading to our Data views.

    The default Parser expects a named arg "filename" in the URL pattern.
    However to be consistent, we override it so that we can use the path or
    uid in the url.
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


class DataUidView(BaseFSView):
    """
    File data view.

    Provides access to the data contained within a file identified by it's uid.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)

    def get(self, request, uid, format=None):
        try:
            file = File.objects.get(uid=uid, user=request.user)
        except File.DoesNotExist:
            raise exceptions.NotFound(uid)
        response = StreamingHttpResponse(self.get_fs().download(file.path),
                                         content_type=file.mime)
        if request.GET.get('download', None):
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % file.name
        return response

    def post(self, request, uid, format=None):
        try:
            file = File.objects.get(uid=uid, user=request.user)
        except File.DoesNotExist:
            raise exceptions.NotFound(uid)
        file = self.get_fs().upload(file.path, f=request.data['file'])
        return response.Response(FileSerializer(file).data)


class DataPathView(BaseFSView):
    """
    File data view.

    Provides access to the data contained within a file identified by it's
    path.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)

    def get(self, request, path, format=None):
        try:
            file = File.objects.get(path=path, user=request.user)
        except File.DoesNotExist:
            raise exceptions.NotFound(path)
        try:
            response = StreamingHttpResponse(self.get_fs().download(path),
                                             content_type=file.mime)
        except FileNotFoundError:
            raise exceptions.NotFound(path)
        if request.GET.get('download', None):
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % file.name
        return response

    def post(self, request, path, format=None):
        file = self.get_fs().upload(path, f=request.data['file'])
        return response.Response(FileSerializer(file).data)
