"""
API views.

This file contains the serializers views and supporting code that produces the
API.
"""

from os.path import basename

from django.db.models import Sum, Count
from django.http import StreamingHttpResponse

from rest_framework import (
    serializers, permissions, views, generics, response, exceptions, parsers,
    mixins
)

from main.fs import MulticloudFilesystem
from main.fs.errors import DirectoryNotFoundError, FileNotFoundError
from main.models import (
    User, BaseStorage, BaseUserStorage, OAuth2Storage, OAuth2UserStorage,
    Directory, File, ChunkStorage, Option, Tag,
)


class BaseStorageSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud.

    Provides statistics for a supported cloud.
    """

    size = serializers.SerializerMethodField()
    used = serializers.SerializerMethodField()
    chunks = serializers.SerializerMethodField()

    class Meta:
        model = BaseStorage
        fields = ('name', 'size', 'used', 'chunks')

    def get_size(self, obj):
        return OAuth2UserStorage.objects.filter(storage=obj).aggregate(
            Sum('size'))['size__sum'] or 0

    def get_used(self, obj):
        return OAuth2UserStorage.objects.filter(storage=obj).aggregate(
            Sum('used'))['used__sum'] or 0

    def get_chunks(self, obj):
        return ChunkStorage.objects.filter(storage__storage=obj).count()


class PublicCloudListView(generics.ListAPIView):
    """
    List Clouds.

    Provides system-wide information/stats about a supported clouds. Used to
    generate menus and graphs on public site.
    """

    permission_classes = [permissions.AllowAny]
    queryset = OAuth2Storage.objects.all()
    serializer_class = BaseStorageSerializer

    def get_queryset(self):
        return BaseStorage.objects.all().order_by('provider')


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


class BaseUserStorageSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud instance.

    Provides statistics for a cloud account.
    """

    name = serializers.CharField(source='storage.name')
    chunks = serializers.SerializerMethodField()

    class Meta:
        model = BaseUserStorage
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
    queryset = BaseUserStorage.objects.all()
    serializer_class = BaseUserStorageSerializer

    def get_queryset(self):
        return BaseUserStorage.objects.filter(user=self.request.user).order_by(
            'storage__provider')


class DirectorySerializer(serializers.ModelSerializer):
    """
    Serialize a Directory.

    Provides details about a directory.
    """

    mime = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = Directory
        fields = ('uid', 'name', 'display_name', 'path', 'display_path',
                  'parents', 'mime', 'created', 'tags', 'attrs')

    def get_mime(self, obj):
        return 'application/x-directory'

    def get_tags(self, obj):
        return obj.tags.all().values_list('name', flat=True)


class FileSerializer(serializers.ModelSerializer):
    """
    Serialize a File.

    Provides details about a File.
    """

    chunks = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    display_path = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = File
        fields = ('uid', 'name', 'display_name', 'extension', 'path',
                  'display_path', 'size', 'chunks', 'md5', 'sha1', 'mime',
                  'created', 'raid_level', 'tags', 'attrs')

    def get_chunks(self, obj):
        # These names are a bit long...
        n1 = 'storage__storage__storage__provider'
        n2 = 'storage__storage__storage'
        chunks = {}
        for item in obj.chunks.values(n1).annotate(Count(n2)):
            chunks[BaseStorage.PROVIDERS[item[n1]]] = \
                item['%s__count' % n2]
        return chunks

    def get_display_name(self, obj):
        return obj.name

    def get_display_path(self, obj):
        return obj.path

    def get_tags(self, obj):
        return obj.tags.all().values_list('name', flat=True)


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


class TagSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud instance.

    Provides statistics for a cloud account.
    """

    class Meta:
        model = Tag
        fields = ('name', )


class TagListView(views.APIView):
    """
    List files with a given set of tags.

    Queries Files with given set of Tags. Used to list files and additional tag
    names in UI.
    """

    def get(self, request, format=None):
        kwargs = {}
        if 'tag' in request.GET:
            kwargs['name__in'] = request.GET.getlist('tag')
        tags = Tag.objects.filter(file__user=request.user, **kwargs)
        tags = tags.annotate(Count('file'))
        tags = tags.values_list('name', 'file__count')
        return response.Response({i[0]: i[1] for i in tags})


class DirectoryTagView(BaseFSView):
    """
    File tag view.

    Provides File information for a file identified by it's tag(s).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, format=None):
        tags = request.GET.get('tag')
        return response.Response(
            DirectorySerializer(
                Directory.objects.filter(tag__name__in=tags)).data)


class FileTagView(generics.ListAPIView):
    """
    File tag view.

    Provides File information for a file identified by it's tag(s).
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        tags = []
        return File.objects.filter(tag__name__in=tags)

    def get(self, request, format=None):
        tags = request.GET.get('tag')
        return response.Response(
            FileSerializer(File.objects.filter(tag__name__in=tags)).data)
