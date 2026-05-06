from django.contrib import admin
from .models import Manager, ProfileChangeRequest


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_id', 'telegram_username', 'email', 'usdt_wallet', 'commission', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('telegram_id', 'telegram_username', 'name', 'email')


@admin.register(ProfileChangeRequest)
class ProfileChangeRequestAdmin(admin.ModelAdmin):
    list_display = ('manager', 'field', 'new_value', 'status', 'created_at')
    list_filter = ('status', 'field')
    search_fields = ('manager__telegram_id', 'manager__name')
    readonly_fields = ('manager', 'field', 'new_value', 'created_at', 'updated_at')
    ordering = ('status', '-created_at')
