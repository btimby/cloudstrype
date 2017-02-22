from django.contrib import admin

from main.models import (
    OAuth2Provider, OAuth2AccessToken
)


class OAuth2ProviderAdmin(admin.ModelAdmin):
    pass


class OAuth2AccessTokenAdmin(admin.ModelAdmin):
    pass


admin.site.register(OAuth2Provider, OAuth2ProviderAdmin)
admin.site.register(OAuth2AccessToken, OAuth2AccessTokenAdmin)
