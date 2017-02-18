from django.conf import settings
from django.conf.urls import (
    url, include
)
from django.views.generic import TemplateView


urlpatterns = [
    url(r'^index.html', TemplateView.as_view(template_name='ui/index.html')),
]
