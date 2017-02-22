from django.conf import settings
from django.conf.urls import (
    url, include
)
from django.contrib.staticfiles.views import serve


urlpatterns = [
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^(?P<path>.*)$', serve),
    ]
