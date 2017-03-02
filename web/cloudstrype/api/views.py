from django.db.models import Sum

from rest_framework import (
    serializers, permissions, views, generics, response
)

from main.fs import MulticloudFilesystem
from main.models import (
    User, OAuth2Provider, OAuth2AccessToken, OAuth2StorageToken
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('uid', 'email', 'full_name', 'first_name', 'last_name')


class OAuth2AccessTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = OAuth2AccessToken
        fields = ('provider', )


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


class OAuth2StorageTokenSerializer(serializers.ModelSerializer):

    name = serializers.CharField(source='token.provider.name')

    class Meta:
        model = OAuth2StorageToken
        fields = ('name', 'size', 'used')


class MeView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    template_name = 'api/me.html'

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class PublicCloudListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    queryset = OAuth2StorageToken.objects.all()
    serializer_class = OAuth2ProviderSerializer

    def get_queryset(self):
        return OAuth2Provider.objects.all()


class CloudListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = OAuth2StorageToken.objects.all()
    serializer_class = OAuth2StorageTokenSerializer

    def get_queryset(self):
        queryset = OAuth2StorageToken.objects.filter(
            user=self.request.user)
        return (o for o in queryset if o.token.provider.is_storage)


class FileListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_fs(self, namespace):
        return MulticloudFilesystem(self.request.user)

    def get(self, request, path, format=None):
        return response.Response(['foo', 'bar'])

    def post(self, request, path, format=None):
        pass
