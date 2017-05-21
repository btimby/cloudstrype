"""
URL mapping for API.
"""

from django.conf.urls import (
    url, include
)

from rest_framework.urlpatterns import format_suffix_patterns

from api.views import (
    MeView, PublicCloudListView, CloudListView, UserDirUidView,
    UserDirPathView, UserFileUidView, UserFilePathView, DataUidView,
    DataPathView, OptionsView, UserDirTagView, UserFileTagView, TagListView,
    TagItemView, FileVersionPathView, FileVersionUidView,
    FileVersionDataUidView
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
    url(r'^v1/me/dirs/by-uid:(.+):$', UserDirUidView.as_view(),
        name='dirs_uid'),
    url(r'^v1/me/dirs/by-path:(/.+):$', UserDirPathView.as_view(),
        name='dirs_path'),
    url(r'^v1/me/dirs/by-tag:(?P<name>.*):$', UserDirTagView.as_view(),
        name='dirtaglist'),

    # File information
    url(r'^v1/me/files/by-uid:(.+):$', UserFileUidView.as_view(),
        name='files_uid'),
    url(r'^v1/me/files/by-path:(/.+):$', UserFilePathView.as_view(),
        name='files_path'),
    url(r'^v1/me/files/by-tag:(?P<name>.*):$', UserFileTagView.as_view(),
        name='filetaglist'),

    # File data (multipart) for browser uploads
    url(r'^v1/me/files/by-uid:(.+):/data/$', DataUidView.as_view(),
        name='files_data_uid'),
    url(r'^v1/me/files/by-path:(/.+):/data/$', DataPathView.as_view(),
        name='files_data_path'),

    # File versions.
    url(r'^v1/me/files/by-uid:(.+):/versions/$', FileVersionUidView.as_view(),
        name='fileversions_uid'),
    url(r'^v1/me/files/by-path:(/.+):/versions/$',
        FileVersionPathView.as_view(),
        name='fileversions_path'),

    # File version data.
    url(r'^v1/me/versions/(.+)/data/$', FileVersionDataUidView.as_view(),
        name='fileversions_data'),

    # Tags
    url(r'^v1/me/tags/$', TagListView.as_view(), name='taglist'),
    url(r'^v1/me/tags/(?P<name>.+)/$', TagItemView.as_view(), name='tagitem'),
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'html'])

urlpatterns += [
    url(r'^rest-auth/', include('rest_auth.urls')),
]
