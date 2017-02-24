from django.conf import settings
from django.conf.urls import (
    url, include
)

from rest_framework.urlpatterns import format_suffix_patterns

from api.views import router, MeView

urlpatterns = [
    url(r'^v1/users/me', MeView.as_view()),
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'html'])

urlpatterns += [
    url(r'^v1/', include(router.urls)),
    url(r'^rest-auth/', include('rest_auth.urls')),
]

