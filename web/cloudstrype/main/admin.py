from django.contrib import admin

from main.models import (
    User, File, Version, Chunk, Storage, Key,
)


class UserAdmin(admin.ModelAdmin):
    fields = ('email', 'full_name', 'last_login', 'is_active', 'is_admin')


class StorageAdmin(admin.ModelAdmin):
    pass


class FileAdmin(admin.ModelAdmin):
    pass


class VersionAdmin(admin.ModelAdmin):
    pass


class ChunkAdmin(admin.ModelAdmin):
    pass


class KeyAdmin(admin.ModelAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(Storage, StorageAdmin)
admin.site.register(File, FileAdmin)
admin.site.register(Version, VersionAdmin)
admin.site.register(Chunk, ChunkAdmin)
admin.site.register(Key, KeyAdmin)
