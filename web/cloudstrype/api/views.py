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

from main.fs import get_fs
from main.fs.errors import (
    DirectoryNotFoundError, FileNotFoundError, PathNotFoundError
)
from main.models import (
    User, BaseStorage, BaseUserStorage, OAuth2Storage, OAuth2UserStorage,
    UserDir, UserFile, ChunkStorage, Option, Tag, Version, FileVersion,
    UserFileView,
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


class UserDirSerializer(serializers.ModelSerializer):
    """
    Serialize a Directory.

    Provides details about a directory.
    """

    mime = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    path = serializers.SerializerMethodField()

    class Meta:
        model = UserDir
        fields = ('uid', 'name', 'path', 'mime', 'created', 'tags', 'attrs')

    def get_mime(self, obj):
        return 'application/x-directory'

    def get_tags(self, obj):
        return obj.tags.all().values_list('name', flat=True)

    def get_path(self, obj):
        # This is not a model attribute, since we are rendering from a FileInfo
        # instance, we must fake it.
        return obj.path


class UserFileSerializer(serializers.ModelSerializer):
    """
    Serialize a File.

    Provides details about a File.
    """

    # TODO: replace with version
    # chunks = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    path = serializers.SerializerMethodField()
    extension = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()

    class Meta:
        model = UserFileView
        fields = ('uid', 'name', 'extension', 'path', 'size', 'md5', 'sha1',
                  'mime', 'created', 'tags', 'attrs', 'version', 'versions')

    def get_chunks(self, obj):
        # These names are a bit long...
        n1 = 'storage__storage__storage__provider'
        n2 = 'storage__storage__storage'
        chunks = {}
        for item in obj.chunks.values(n1).annotate(Count(n2)):
            chunks[BaseStorage.PROVIDERS[item[n1]]] = \
                item['%s__count' % n2]
        return chunks

    def get_tags(self, obj):
        return obj.tags.all().values_list('name', flat=True)

    def get_path(self, obj):
        # This is not a model attribute, since we are rendering from a FileInfo
        # instance, we must fake it.
        return obj.path

    def get_extension(self, obj):
        # This is not a model attribute, since we are rendering from a FileInfo
        # instance, we must fake it.
        return obj.extension

    def get_version(self, obj):
        return obj.version_uid


class FileVersionSerializer(serializers.ModelSerializer):
    """
    Serialize a File version.

    Provides details about a version of a file.
    """

    class Meta:
        model = FileVersion
        fields = ('uid', 'size', 'md5', 'sha1', 'mime', 'created')

    size = serializers.IntegerField(source='version.size')
    md5 = serializers.CharField(source='version.md5')
    sha1 = serializers.CharField(source='version.sha1')
    mime = serializers.CharField(source='version.mime')


class UserDirListingSerializer(serializers.Serializer):
    """
    Serialize a Directory and it's contents.

    Provides details about a Directory as well as a listing of Directories and
    files contained within it.
    """

    info = UserDirSerializer()
    dirs = UserDirSerializer(many=True)
    files = UserFileSerializer(many=True)


class UserDirUidView(views.APIView):
    """
    Directory detail view.

    Provides Directory listing for a directory identified by it's uid.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            dir = UserDir.objects.get(uid=uid, user=request.user)
        except UserDir.DoesNotExist:
            raise exceptions.NotFound(uid)
        dir, dirs, files = fs.listdir(dir.path, dir=dir)
        return response.Response(UserDirListingSerializer({
            'info': dir, 'dirs': dirs, 'files': files
        }).data)

    def delete(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            dir = UserDir.objects.get(uid=uid, user=request.user)
        except UserDir.DoesNotExist:
            raise exceptions.NotFound(uid)
        try:
            return response.Response(
                fs.rmdir(dir.path, dir=dir))
        except DirectoryNotFoundError:
            raise exceptions.NotFound(uid)


class UserDirPathView(views.APIView):
    """
    Directory detail view.

    Provides Directory listing for a directory identified by it's path.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, path, format=None):
        try:
            dir, dirs, files = get_fs(request.user).listdir(path)
        except DirectoryNotFoundError:
            raise exceptions.NotFound()
        return response.Response(UserDirListingSerializer({
            'info': dir, 'dirs': dirs, 'files': files
        }).data)

    def post(self, request, path, format=None):
        return response.Response(
            UserDirSerializer(get_fs(request.user).mkdir(path)).data)

    def delete(self, request, path, format=None):
        fs = get_fs(request.user)
        if path == '/':
            raise exceptions.ValidationError('Cannot delete root')
        try:
            return response.Response(fs.rmdir(path))
        except DirectoryNotFoundError:
            raise exceptions.NotFound(path)


class UserFileUidView(views.APIView):
    """
    File detail view.

    Provides File information for a file identified by it's uid.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            file = UserFile.objects.get(uid=uid, user=request.user)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)
        return response.Response(
            UserFileSerializer(fs.info(file.path, file=file)).data)

    def delete(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            file = UserFile.objects.get(uid=uid, user=request.user)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)
        return response.Response(
            fs.delete(file.path, file=file))


class UserFilePathView(views.APIView):
    """
    File detail view.

    Provides File information for a file identified by it's path.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, path, format=None):
        fs = get_fs(request.user)
        try:
            return response.Response(
                UserFileSerializer(fs.info(path)).data)
        except PathNotFoundError:
            raise exceptions.NotFound(path)

    def delete(self, request, path, format=None):
        fs = get_fs(request.user)
        try:
            return response.Response(fs.delete(path))
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
                return UserFile.objects.get(uid=id, user=request.user).name
            except UserFile.DoesNotExist:
                return
        return basename(id)


class DataUidView(views.APIView):
    """
    File data view.

    Provides access to the data contained within a file identified by it's uid.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)

    def get(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            file = UserFile.objects.get(uid=uid, user=request.user)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)
        response = StreamingHttpResponse(
            fs.download(file.path, file=file),
            content_type=file.mime)
        if request.GET.get('download', None):
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % file.name
        return response

    def post(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            file = UserFile.objects.get(uid=uid, user=request.user)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)
        file = fs.upload(
            file.path, f=request.data['file'])
        return response.Response(UserFileSerializer(file).data)


class DataPathView(views.APIView):
    """
    File data view.

    Provides access to the data contained within a file identified by it's
    path.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)

    def get(self, request, path, format=None):
        fs = get_fs(request.user)
        try:
            file = fs.info(path).obj
        except FileNotFoundError:
            raise exceptions.NotFound(path)
        try:
            response = StreamingHttpResponse(fs.download(path, file=file),
                                             content_type=file.mime)
        except FileNotFoundError:
            raise exceptions.NotFound(path)
        if request.GET.get('download', None):
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % file.name
        return response

    def post(self, request, path, format=None):
        fs = get_fs(request.user)
        file = fs.upload(path, f=request.data['file'])
        return response.Response(UserFileSerializer(file).data)


class FileVersionUidView(views.APIView):
    def get(self, request, uid, format=None):
        try:
            file = UserFile.objects.get(uid=uid)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)
        return response.Response(
            FileVersionSerializer(FileVersion.objects.filter(file=file),
                                  many=True).data)


class FileVersionPathView(views.APIView):
    def get(self, request, path, format=None):
        fs = get_fs(request.user)
        try:
            file = fs.info(path).obj
        except FileNotFoundError:
            raise exceptions.NotFound(path)
        return response.Response(
            FileVersionSerializer(FileVersion.objects.filter(file=file),
                                  many=True).data)


class FileVersionDataUidView(views.APIView):
    def get(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            version = FileVersion.objects.get(uid=uid)
        except Version.DoesNotExist:
            raise exceptions.NotFound(uid)
        file = version.file
        response = StreamingHttpResponse(
            fs.download(file.path, file=file, version=version.version),
            content_type=version.version.mime)
        if request.GET.get('download', None):
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % file.name
        return response


class TagSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud instance.

    Provides statistics for a cloud account.
    """

    class Meta:
        model = Tag
        fields = ('name', )


class TagListView(generics.ListCreateAPIView):
    """
    Tag view.

    Provides interface for managing tag collection.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TagSerializer
    queryset = Tag.objects.all()


class TagItemView(generics.RetrieveUpdateDestroyAPIView):
    """
    Tag view.

    Provides interface for managing individual tags.
    """

    permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TagSerializer
    queryset = Tag.objects.all()
    lookup_field = 'name'


class UserDirTagView(generics.ListAPIView):
    """
    File tag view.

    Provides File information for a file identified by it's tag(s).
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserDirSerializer

    def get_queryset(self):
        return UserDir.objects.filter(
                user=self.request.user, tags__name=self.kwargs['name'])


class UserFileTagView(generics.ListAPIView):
    """
    File tag view.

    Provides File information for a file identified by it's tag(s).
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserFileSerializer

    def get_queryset(self):
        return UserFile.objects.filter(
            user=self.request.user, tags__name=self.kwargs['name'])
