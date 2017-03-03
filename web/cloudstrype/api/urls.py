from django.conf.urls import (
    url, include
)

from rest_framework.urlpatterns import format_suffix_patterns

from api.views import (
    MeView, PublicCloudListView, CloudListView, DirectoryUidView,
    DirectoryPathView, FileUidView, FilePathView, DataUidView, DataPathView,
)

urlpatterns = [
    # Public access
    # -------------
    url(r'^v1/public/clouds/', PublicCloudListView.as_view()),

    # Authenticated access
    # --------------------
    # General
    url(r'^v1/me/', MeView.as_view()),
    url(r'^v1/clouds/', CloudListView.as_view()),

    # Directories
    url(r'^v1/dir/:uid:(.*)$', DirectoryUidView.as_view()),
    url(r'^v1/dir/:path:(/.*)$', DirectoryPathView.as_view()),

    # File information
    url(r'^v1/file/:uid:(.*)$', FileUidView.as_view()),
    url(r'^v1/file/:path:(/.*)$', FilePathView.as_view()),

    # File data (multipart) for browser uploads
    url(r'^v1/data/:uid:(.*)$', DataUidView.as_view()),
    url(r'^v1/data/:path:(/.*)$', DataPathView.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'html'])

urlpatterns += [
    url(r'^rest-auth/', include('rest_auth.urls')),
]
