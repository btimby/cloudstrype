from django.shortcuts import render

from rest_framework import (
    routers, serializers, permissions, viewsets
)
from oauth2_provider.ext.rest_framework import TokenHasReadWriteScope, TokenHasScope

from main.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User


class UserViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, TokenHasReadWriteScope]
    queryset = User.objects.all()
    serializer_class = UserSerializer


router = routers.DefaultRouter()
router.register(r'users', UserViewSet)