from django.contrib import admin

from main.models import (
    OAuth2Provider, OAuth2AccessToken, OAuth2LoginToken, User
)


class UserAdmin(admin.ModelAdmin):
    pass


class OAuth2ProviderAdmin(admin.ModelAdmin):
    pass


class OAuth2AccessTokenAdmin(admin.ModelAdmin):
    pass


class OAuth2LoginTokenAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(OAuth2Provider, OAuth2ProviderAdmin)
admin.site.register(OAuth2AccessToken, OAuth2AccessTokenAdmin)
admin.site.register(OAuth2LoginToken, OAuth2LoginTokenAdmin)
