from django.conf import settings
from django.conf.urls import url
from django.contrib.staticfiles.views import serve
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^$', TemplateView.as_view(template_name='ui/index.html')),
    url(r'^start/$', TemplateView.as_view(template_name='ui/start.html')),
]

if settings.DEBUG:
    urlpatterns += [
        url(r'^(?P<path>.*)$', serve),
    ]
