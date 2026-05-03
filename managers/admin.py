from django.contrib import admin
from .models import Manager


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_id', 'telegram_username', 'email', 'commission', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('telegram_id', 'telegram_username', 'name', 'email')
