from rest_framework import (
    serializers, permissions, views, generics, response
)
from main.models import (
    User, OAuth2Provider, OAuth2AccessToken
)
from main.fs import MulticloudManager


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'uid', 'email')


class OAuth2AccessTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = OAuth2AccessToken
        fields = ('provider', )


class OAuth2ProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = OAuth2Provider
        fields = ('name', )


class MeView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    template_name = 'api/me.html'

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)


class CloudListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    queryset = OAuth2Provider.objects.all()
    serializer_class = OAuth2ProviderSerializer

    def get_queryset(self):
        queryset = OAuth2Provider.objects.filter(
            tokens__user=self.request.user)
        return (o for o in queryset if o.is_storage())


class FileListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_manager(self, namespace):
        tokens = OAuth2AccessToken.objects.filter(user=self.request.user)
        tokens = [o for o in tokens if o.provider.is_storage()]
        clouds = [o.get_client() for o in tokens]
        return MulticloudManager(namespace, clouds)

    def get(self, request, path, format=None):
        return response.Response(['foo', 'bar'])

    def post(self, request, path, format=None):
        pass
