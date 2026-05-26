from decimal import Decimal

from django.contrib import admin

from core.admin import EditLinkMixin
from .services import get_usdt_rate
from .models import Payment, Withdrawal


@admin.register(Payment)
class PaymentAdmin(EditLinkMixin, admin.ModelAdmin):
    list_display = ('manager', 'amount', 'currency', 'status', 'is_settled', 'order_id', 'transaction_id', 'created_at', 'edit_link')
    list_filter = ('status', 'is_settled', 'currency')
    search_fields = ('manager__telegram_id', 'manager__name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Withdrawal)
class WithdrawalAdmin(EditLinkMixin, admin.ModelAdmin):
    list_display = ('manager', 'amount', 'usdt_amount_display', 'status', 'usdt_wallet', 'created_at', 'updated_at', 'edit_link')
    list_filter = ('status',)
    search_fields = ('manager__telegram_id', 'manager__name')
    readonly_fields = ('manager', 'amount', 'usdt_amount', 'usdt_rate', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if change and obj.status == Withdrawal.Status.COMPLETED and obj.usdt_amount is None:
            rate = get_usdt_rate()
            if rate > 0:
                obj.usdt_rate = rate
                obj.usdt_amount = (obj.amount / rate).quantize(Decimal('0.01'))
        super().save_model(request, obj, form, change)

    @admin.display(description='Сумма USDT')
    def usdt_amount_display(self, obj):
        if obj.usdt_amount is not None:
            return f'{obj.usdt_amount} USDT'
        rate = get_usdt_rate()
        if rate > 0:
            live = (obj.amount / rate).quantize(Decimal('0.01'))
            return f'~{live} USDT'
        return '—'

    @admin.display(description='USDT кошелёк')
    def usdt_wallet(self, obj):
        return obj.manager.usdt_wallet or '—'
