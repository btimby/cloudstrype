from django.contrib import admin

from main.models import (
    OAuth2Provider, OAuth2AccessToken, User
)


class UserAdmin(admin.ModelAdmin):
    fields = ('email', 'full_name', 'last_login', 'is_active', 'is_admin')


class OAuth2ProviderAdmin(admin.ModelAdmin):
    pass


class OAuth2AccessTokenAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(OAuth2Provider, OAuth2ProviderAdmin)
admin.site.register(OAuth2AccessToken, OAuth2AccessTokenAdmin)
