from django.conf import settings
from django.conf.urls import (
    url, include
)

from api.views import router


urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^rest-auth/', include('rest_auth.urls'))
]
