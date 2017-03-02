from django.contrib import admin

from main.models import (
    OAuth2Provider, OAuth2AccessToken, OAuth2LoginToken, OAuth2StorageToken,
    User
)


class UserAdmin(admin.ModelAdmin):
    fields = ('email', 'full_name', 'last_login', 'is_active', 'is_admin')


class OAuth2ProviderAdmin(admin.ModelAdmin):
    pass


class OAuth2AccessTokenAdmin(admin.ModelAdmin):
    pass


class OAuth2LoginTokenAdmin(admin.ModelAdmin):
    pass


class OAuth2StorageTokenAdmin(admin.ModelAdmin):
    readonly_fields = ('attrs',)


admin.site.register(User, UserAdmin)
admin.site.register(OAuth2Provider, OAuth2ProviderAdmin)
admin.site.register(OAuth2AccessToken, OAuth2AccessTokenAdmin)
admin.site.register(OAuth2LoginToken, OAuth2LoginTokenAdmin)
admin.site.register(OAuth2StorageToken, OAuth2StorageTokenAdmin)
