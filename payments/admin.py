from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('manager', 'amount', 'currency', 'status', 'order_id', 'transaction_id', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('manager__telegram_id', 'manager__name', 'description')
    readonly_fields = ('created_at', 'updated_at')
