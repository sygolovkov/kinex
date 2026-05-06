from django.contrib import admin

from core.admin import EditLinkMixin
from .models import Manager, ProfileChangeRequest


@admin.register(Manager)
class ManagerAdmin(EditLinkMixin, admin.ModelAdmin):
    list_display = ('name', 'telegram_id', 'telegram_username', 'email', 'usdt_wallet', 'commission', 'is_active', 'edit_link')
    list_filter = ('is_active',)
    search_fields = ('telegram_id', 'telegram_username', 'name', 'email')


@admin.register(ProfileChangeRequest)
class ProfileChangeRequestAdmin(EditLinkMixin, admin.ModelAdmin):
    list_display = ('manager', 'field', 'new_value', 'status', 'created_at', 'edit_link')
    list_filter = ('status', 'field')
    search_fields = ('manager__telegram_id', 'manager__name')
    readonly_fields = ('manager', 'field', 'new_value', 'created_at', 'updated_at')
    ordering = ('status', '-created_at')
