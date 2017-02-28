from django.conf.urls import (
    url, include
)
from django.contrib import admin


urlpatterns = [
    # Contrib urls
    url(r'^admin/', admin.site.urls),

    # Third party urls
    url(r'^oauth2/', include('oauth2_provider.urls',
        namespace='oauth2_provider')),

    # Application urls
    url(r'^api/', include('api.urls', namespace='api')),
    url(r'^main/', include('main.urls', namespace='main')),
    url(r'^', include('ui.urls', namespace='ui')),
]
