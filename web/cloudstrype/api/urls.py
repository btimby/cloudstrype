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
    OptionsView, DirectoryTagView, FileTagView, TagListView,
)

urlpatterns = [
    # Public access
    # -------------
    url(r'^v1/clouds/', PublicCloudListView.as_view(), name='public_clouds'),

    # Authenticated access
    # --------------------
    # General
    url(r'^v1/me/$', MeView.as_view(), name='me'),
    url(r'^v1/me/clouds/$', CloudListView.as_view(), name='clouds'),
    url(r'^v1/me/options/$', OptionsView.as_view(), name='options'),

    # Directories
    url(r'^v1/me/dirs/uid:(.*):$', DirectoryUidView.as_view(),
        name='dirs_uid'),
    url(r'^v1/me/dirs/path:(/.*):$', DirectoryPathView.as_view(),
        name='dirs_path'),
    url(r'^v1/me/dirs/tags/', DirectoryTagView.as_view(), name='dirs_tags'),

    # File information
    url(r'^v1/me/files/uid:(.*):$', FileUidView.as_view(), name='files_uid'),
    url(r'^v1/me/files/path:(/.*):$', FilePathView.as_view(),
        name='files_path'),
    url(r'^v1/me/files/tags/', FileTagView.as_view(), name='files_tags'),

    # File data (multipart) for browser uploads
    url(r'^v1/me/files/uid:(.*):/data/$', DataUidView.as_view(),
        name='files_data_uid'),
    url(r'^v1/me/files/path:(/.*):/data/$', DataPathView.as_view(),
        name='files_data_path'),

    # Tags
    url(r'^v1/me/tags/', TagListView.as_view(), name='tags'),
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'html'])

urlpatterns += [
    url(r'^rest-auth/', include('rest_auth.urls')),
]
