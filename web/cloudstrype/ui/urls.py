"""
URL mapping for user interface.
"""

from django.conf import settings
from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.views import serve
from django.views.generic import TemplateView

from ui.views import HowView


urlpatterns = [
    url(r'^$', TemplateView.as_view(template_name='ui/index.html'),
        name='home'),
    url(r'^how/(?P<step>[0-9]{1})/$', HowView.as_view(), name='how'),
    url(r'^app/$',
        login_required()(TemplateView.as_view(template_name='ui/app.html')),
        name='app'),
    url(r'^new/$',
        login_required()(TemplateView.as_view(template_name='ui/new.html')),
        name='new'),
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^(?P<path>.*)$', serve),
    ]
