from django.contrib import admin
from .models import Manager


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'name', 'email', 'commission', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('telegram_id', 'name', 'email')
