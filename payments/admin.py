from django.contrib import admin
from .models import Payment, Withdrawal


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('manager', 'amount', 'currency', 'status', 'is_settled', 'order_id', 'transaction_id', 'created_at')
    list_filter = ('status', 'is_settled', 'currency')
    search_fields = ('manager__telegram_id', 'manager__name', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = ('manager', 'amount', 'status', 'usdt_wallet', 'created_at', 'updated_at')
    list_filter = ('status',)
    search_fields = ('manager__telegram_id', 'manager__name')
    readonly_fields = ('manager', 'amount', 'created_at', 'updated_at')

    @admin.display(description='USDT кошелёк')
    def usdt_wallet(self, obj):
        return obj.manager.usdt_wallet or '—'
