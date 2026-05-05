from django.contrib import admin
from .models import Settings


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    fields = ('admin_telegram_username', 'bot_id', 'payment_system_commission')

    def has_add_permission(self, request):
        return not Settings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
