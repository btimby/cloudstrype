"""
URL mapping for API.
"""

from django.conf.urls import (
    url, include
)

from rest_framework.urlpatterns import format_suffix_patterns

from api.views import (
    MeView, PublicCloudListView, CloudListView, DirectoryUidView,
    DirectoryPathView, FileUidView, FilePathView, DataUidView, DataPathView,
    OptionsView,
)

urlpatterns = [
    # Public access
    # -------------
    url(r'^v1/clouds/', PublicCloudListView.as_view()),

    # Authenticated access
    # --------------------
    # General
    url(r'^v1/me/$', MeView.as_view()),
    url(r'^v1/me/clouds/$', CloudListView.as_view()),
    url(r'^v1/me/options/$', OptionsView.as_view()),

    # Directories
    url(r'^v1/me/dirs/uid:(.*):$', DirectoryUidView.as_view()),
    url(r'^v1/me/dirs/path:(/.*):$', DirectoryPathView.as_view()),

    # File information
    url(r'^v1/me/files/uid:(.*):$', FileUidView.as_view()),
    url(r'^v1/me/files/path:(/.*):$', FilePathView.as_view()),

    # File data (multipart) for browser uploads
    url(r'^v1/me/files/uid:(.*):/data/$', DataUidView.as_view()),
    url(r'^v1/me/files/path:(/.*):/data/$', DataPathView.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'html'])

urlpatterns += [
    url(r'^rest-auth/', include('rest_auth.urls')),
]
