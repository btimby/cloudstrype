from django.conf import settings
from django.conf.urls import (
    url, include
)
from django.contrib import admin
from django.contrib.staticfiles.views import serve
from django.views.generic import (
    RedirectView, TemplateView
)


urlpatterns = [
    # Contrib urls
    url(r'^admin/', admin.site.urls),

    # Third party urls
    url(r'^oauth2/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    url(r'^accounts/', include('allauth.urls')),

    # Application urls
    url(r'^api/', include('api.urls', namespace='api')),

    # Top-level urls
    url(r'^$', RedirectView.as_view(url='/static/html/index.html')),
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^static/(?P<path>.*)$', serve),
    ]
