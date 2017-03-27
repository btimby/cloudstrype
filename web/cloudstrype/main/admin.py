from django.contrib import admin

from main.models import (
    BaseStorage, OAuth2Storage, User
)


class UserAdmin(admin.ModelAdmin):
    fields = ('email', 'full_name', 'last_login', 'is_active', 'is_admin')


class BaseStorageAdmin(admin.ModelAdmin):
    pass


class OAuth2StorageAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(BaseStorage, BaseStorageAdmin)
admin.site.register(OAuth2Storage, OAuth2StorageAdmin)
