from django.contrib import admin

from main.models import (
    User, BaseStorage, OAuth2Storage, OAuth2UserStorage, ArrayUserStorage,
    File, Version, Chunk, 
)


class UserAdmin(admin.ModelAdmin):
    fields = ('email', 'full_name', 'last_login', 'is_active', 'is_admin')


class BaseStorageAdmin(admin.ModelAdmin):
    pass


class OAuth2StorageAdmin(admin.ModelAdmin):
    pass


class OAuth2UserStorageAdmin(admin.ModelAdmin):
    pass


class ArrayUserStorageAdmin(admin.ModelAdmin):
    pass


class FileAdmin(admin.ModelAdmin):
    pass


class VersionAdmin(admin.ModelAdmin):
    pass


class ChunkAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(BaseStorage, BaseStorageAdmin)
admin.site.register(OAuth2Storage, OAuth2StorageAdmin)
admin.site.register(OAuth2UserStorage, OAuth2UserStorageAdmin)
admin.site.register(ArrayUserStorage, ArrayUserStorageAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Version, VersionAdmin)
admin.site.register(Chunk, ChunkAdmin)
