from django.conf.urls import url

from main.views import (
    Login, LoginComplete, Logout, EmailConfirm
)


urlpatterns = [
    url(r'^login/(\w+)/$', Login.as_view(), name='login_begin'),
    url(r'^login/(\w+)/complete/$', LoginComplete.as_view(),
        name='login_complete'),
    url(r'^email/confirm/(?P<uid>[0-9A-Za-z_\-\.]+)/'
        r'(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        EmailConfirm.as_view(), name='email_confirm'),

    url(r'^logout/', Logout.as_view()),
]
