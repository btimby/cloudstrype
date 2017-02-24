from django.conf.urls import (
    url, include
)
from django.contrib import admin
from django.views.generic import RedirectView


urlpatterns = [
    # Contrib urls
    url(r'^admin/', admin.site.urls),

    # Third party urls
    url(r'^oauth2/', include('oauth2_provider.urls',
        namespace='oauth2_provider')),

    # Application urls
    url(r'^api/', include('api.urls', namespace='api')),
    url(r'^static/', include('ui.urls', namespace='ui')),
    url(r'^main/', include('main.urls', namespace='main')),

    # Top-level urls
    url(r'^$', RedirectView.as_view(url='/static/html/index.html')),
]
