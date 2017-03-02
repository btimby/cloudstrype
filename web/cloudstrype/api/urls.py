from django.conf.urls import (
    url, include
)

from rest_framework.urlpatterns import format_suffix_patterns

from api.views import (
    MeView, PublicCloudListView, CloudListView, FileListView
)

urlpatterns = [
    url(r'^v1/users/me', MeView.as_view()),
    url(r'^v1/public/clouds/', PublicCloudListView.as_view()),
    url(r'^v1/clouds/', CloudListView.as_view()),
    url(r'^v1/files(/.*)$', FileListView.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'html'])

urlpatterns += [
    url(r'^rest-auth/', include('rest_auth.urls')),
]
