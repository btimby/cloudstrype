from django.conf.urls import (
    url, include
)
from django.contrib import admin

from main.views import (
    login, logout, Login, LoginComplete
)


urlpatterns = [
    # Contrib urls
    url(r'^admin/', admin.site.urls),

    # Third party urls
    url(r'^oauth2/', include('oauth2_provider.urls',
        namespace='oauth2_provider')),

    # Application urls
    url(r'^accounts/login/$', login, name='login'),
    url(r'^accounts/logout/$', logout),
    url(r'^accounts/login/(\w+)/$', Login.as_view(), name='login_oauth2'),
    url(r'^accounts/login/(\w+)/complete/$', LoginComplete.as_view(),
        name='complete_oauth2'),
    url(r'^api/', include('api.urls', namespace='api')),
    url(r'^', include('ui.urls', namespace='ui')),
]
