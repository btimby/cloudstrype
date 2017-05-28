"""
API views.

This file contains the serializers views and supporting code that produces the
API.
"""

from os.path import basename

from django import forms
from django.db.models import Sum, Count
from django.http import StreamingHttpResponse

from rest_framework import (
    serializers, permissions, views, generics, response, exceptions, parsers,
    mixins, renderers
)

from main.fs import get_fs
from main.fs.errors import (
    DirectoryNotFoundError, FileNotFoundError, PathNotFoundError
)
from main.models import (
    User, Storage, UserDir, UserFile, ChunkStorage, Option, Tag, Version,
    FileVersion,
)


class StorageSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud.

    Provides statistics for a supported cloud.
    """

    chunks = serializers.SerializerMethodField()

    class Meta:
        model = Storage
        fields = ('name', 'size', 'used', 'chunks')

    def get_chunks(self, obj):
        return ChunkStorage.objects.filter(storage=obj).count()


class PublicCloudListView(generics.ListAPIView):
    """
    List Clouds.

    Provides system-wide information/stats about a supported clouds. Used to
    generate menus and graphs on public site.
    """

    permission_classes = [permissions.AllowAny]
    queryset = Storage.objects.all()
    serializer_class = StorageSerializer

    def get_queryset(self):
        return Storage.objects.all().order_by('type')


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


class StorageSerializer(serializers.ModelSerializer):
    """
    Serialize a Cloud instance.

    Provides statistics for a cloud account.
    """

    chunks = serializers.SerializerMethodField()

    class Meta:
        model = Storage
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
    queryset = Storage.objects.all()
    serializer_class = StorageSerializer

    def get_queryset(self):
        return Storage.objects.filter(user=self.request.user).order_by('type')


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


class VersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Version
        fields = ('uid', 'size', 'md5', 'sha1', 'mime', 'created')


class UserFileSerializer(serializers.ModelSerializer):
    """
    Serialize a File.

    Provides details about a File.
    """

    chunks = serializers.SerializerMethodField()
    shared_with = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()
    versions = serializers.SerializerMethodField()

    size = serializers.IntegerField(source='file.version.size')
    md5 = serializers.CharField(source='file.version.md5')
    sha1 = serializers.CharField(source='file.version.sha1')
    mime = serializers.CharField(source='file.version.mime')
    created = serializers.DateTimeField(source='file.created')

    class Meta:
        model = UserFile
        fields = ('uid', 'name', 'extension', 'path', 'size', 'md5', 'sha1',
                  'mime', 'created', 'tags', 'attrs', 'version', 'versions',
                  'chunks', 'shared_with')

    def get_chunks(self, obj):
        # These names are a bit long...
        n1 = 'storages__storage__type'
        n2 = 'storages__storage'
        chunks = {}
        for item in obj.file.version.chunks.values(n1).annotate(Count(n2)):
            chunks[Storage.TYPES[item[n1]]] = \
                item['%s__count' % n2]
        return chunks

    def get_shared_with(self, obj):
        return UserSerializer(
            UserFile.objects.filter(file=obj.file) \
                .exclude(user=obj.file.owner) \
                .exclude(user=obj.user),
            many=True).data

    def get_tags(self, obj):
        return obj.tags.all().values_list('name', flat=True)

    def get_version(self, obj):
        return VersionSerializer(obj.file.version).data

    def get_versions(self, obj):
        return VersionSerializer(obj.file.versions.all(), many=True).data


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
            raise exceptions.NotFound(path)
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
            info = fs.info(path)
            if info.isdir:
                raise exceptions.NotFound(path)
            return response.Response(
                UserFileSerializer(info).data)
        except PathNotFoundError:
            raise exceptions.NotFound(path)

    def delete(self, request, path, format=None):
        fs = get_fs(request.user)
        try:
            info = fs.info(path)
            if info.isdir:
                raise exceptions.NotFound(path)
            return response.Response(fs.delete(path, file=info))
        except PathNotFoundError:
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
            uid = parser_context['args'][0]
        except (KeyError, IndexError):
            return
        if not uid.startswith('/'):
            try:
                return UserFile.objects.get(uid=uid, user=request.user).name
            except UserFile.DoesNotExist:
                return
        return basename(uid)


class UploadForm(forms.Form):
    file = forms.FileField()


class UploadBrowsableAPIRenderer(renderers.BrowsableAPIRenderer):
    def get_context(self, *args, **kwargs):
        context = super().get_context(*args, **kwargs)
        context['post_form'] = UploadForm()
        return context


class DataUidVersionView(views.APIView):
    """
    File data view.

    Provides access to the data contained within a file identified by it's uid.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)
    renderer_classes = (UploadBrowsableAPIRenderer, renderers.JSONRenderer)

    def get(self, request, uid, version, format=None):
        fs = get_fs(request.user)

        # Find requested file.
        try:
            file = UserFile.objects.get(uid=uid, user=request.user)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)

        # Find requested version.
        try:
            version = file.file.versions.get(uid=version)
        except Version.DoesNotExist:
            raise exceptions.NotFound(version)

        # Prepare response.
        response = StreamingHttpResponse(
            fs.download(file.path, file=file, version=version),
            content_type=version.mime)

        # Adjust headers
        if 'download' in request.GET:
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % file.name

        # Send the file.
        return response

class DataUidView(DataUidVersionView):
    def get(self, request, uid, format=None):
        fs = get_fs(request.user)

        # Find requested file.
        try:
            file = UserFile.objects.get(uid=uid, user=request.user)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)

        return super().get(request, uid, file.file.version.uid, format)

    def post(self, request, uid, format=None):
        fs = get_fs(request.user)
        try:
            file = UserFile.objects.get(uid=uid, user=request.user)
        except UserFile.DoesNotExist:
            raise exceptions.NotFound(uid)
        file = fs.upload(
            file.path, f=request.FILES['file'])
        return response.Response(UserFileSerializer(file).data)


class DataPathVersionView(views.APIView):
    """
    File data view.

    Provides access to the data contained within a file identified by it's
    path.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = (UrlUidFilenameUploadParser,)
    renderer_classes = (UploadBrowsableAPIRenderer, renderers.JSONRenderer)

    def get(self, request, path, version, format=None):
        fs = get_fs(request.user)

        # Find requested file.
        try:
            file = fs.info(path)
        except PathNotFoundError:
            raise exceptions.NotFound(path)

        # Find requested version.
        try:
            version = file.file.versions.get(uid=version)
        except Version.DoesNotExist:
            raise exceptions.NotFound(version)

        # Prepare response.
        try:
            response = StreamingHttpResponse(
                fs.download(path, file=file, version=version),
                content_type=version.mime)
        except PathNotFoundError:
            raise exceptions.NotFound(path)

        # Adjust headers.
        if 'download' in request.GET:
            response['Content-Disposition'] = \
                'attachment; filename="%s"' % file.name

        # Send the file.
        return response


class DataPathView(DataPathVersionView):
    def get(self, request, path, format=None):
        fs = get_fs(request.user)

        try:
            file = fs.info(path)
        except PathNotFoundError:
            raise exceptions.NotFound(path)

        return super().get(request, path, file.file.version.uid, format)

    def post(self, request, path, format=None):
        fs = get_fs(request.user)
        file = fs.upload(path, f=request.FILES['file'])
        return response.Response(UserFileSerializer(file).data)


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
