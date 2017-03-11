"""
URL mapping for user interface.
"""

from django.conf import settings
from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.views import serve
from django.views.generic import TemplateView

urlpatterns = [
    url(r'^$', TemplateView.as_view(template_name='ui/index.html'),
        name='home'),
    url(r'^start/$', TemplateView.as_view(template_name='ui/start.html'),
        name='start'),
    url(r'^login/$', TemplateView.as_view(template_name='ui/login.html'),
        name='login'),
    url(r'^app/$',
        login_required()(TemplateView.as_view(template_name='ui/app.html')),
        name='app'),
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^(?P<path>.*)$', serve),
    ]
