from django.contrib import admin

from main.models import (
    Provider, ProviderOAuth, Storage
)


class ProviderOAuthAdmin(admin.StackedInline):
    model = ProviderOAuth


class ProviderAdmin(admin.ModelAdmin):
    inlines = (ProviderOAuthAdmin, )


admin.site.register(Provider, ProviderAdmin)
