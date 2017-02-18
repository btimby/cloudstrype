from django.conf import settings
from django.conf.urls import (
    url, include
)
from django.contrib import admin
from django.contrib.staticfiles.views import serve as serve_static


urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^static/(?P<path>.*)$', serve_static),
    ]
