from django.conf import settings
from django.conf.urls import (
    url, include
)

from main.views import (
    Login, LoginComplete, Logout
)


urlpatterns = [
    url(r'^login/(\w+)/$', Login.as_view(), name='login_begin'),
    url(r'^login/(\w+)/complete/$', LoginComplete.as_view(),
        name='login_complete'),

    url(r'^logout/', Logout.as_view()),
]
