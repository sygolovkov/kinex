from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Settings


class EditLinkMixin:
    """Добавляет колонку с иконкой редактирования в changelist."""

    def edit_link(self, obj):
        app  = obj._meta.app_label
        name = obj._meta.model_name
        url  = reverse(f'admin:{app}_{name}_change', args=[obj.pk])
        return format_html('<a href="{}" class="changelink">Изменить</a>', url)

    edit_link.short_description = ''  # type: ignore[attr-defined]


def _calc_profit(qs):
    result = qs.filter(
        status__in=[2],  # SUCCESS
        manager__isnull=False,
    ).annotate(
        ca=ExpressionWrapper(
            F('amount') * F('manager__commission') / 100,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).aggregate(total=Sum('ca'))['total']
    return (result or Decimal('0')).quantize(Decimal('0.01'))


def _dynamics(current, previous):
    if previous and previous > 0:
        return round(float((current - previous) / previous * 100), 1)
    return None


def _get_dashboard_stats():
    from managers.models import Manager, ProfileChangeRequest
    from payments.models import Payment, Withdrawal
    from payments.services import get_usdt_rate

    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday       = today - timedelta(days=1)
    week_start      = today - timedelta(days=7)
    prev_week_start = today - timedelta(days=14)
    month_start     = today.replace(day=1)
    if today.month == 1:
        prev_month_start = today.replace(year=today.year - 1, month=12, day=1)
    else:
        prev_month_start = today.replace(month=today.month - 1, day=1)

    managers = Manager.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
    )

    def pay_agg(qs):
        return qs.filter(status=Payment.Status.SUCCESS).aggregate(
            s=Sum('amount'), c=Count('id'),
        )

    pay_today = pay_agg(Payment.objects.filter(created_at__gte=today))
    pay_month = pay_agg(Payment.objects.filter(created_at__gte=month_start))

    all_payments = Payment.objects
    profit_today      = _calc_profit(all_payments.filter(created_at__gte=today))
    profit_yesterday  = _calc_profit(all_payments.filter(created_at__gte=yesterday, created_at__lt=today))
    profit_week       = _calc_profit(all_payments.filter(created_at__gte=week_start))
    profit_prev_week  = _calc_profit(all_payments.filter(created_at__gte=prev_week_start, created_at__lt=week_start))
    profit_month      = _calc_profit(all_payments.filter(created_at__gte=month_start))
    profit_prev_month = _calc_profit(all_payments.filter(created_at__gte=prev_month_start, created_at__lt=month_start))

    usdt_rate = get_usdt_rate()

    def to_usdt(rub):
        if usdt_rate > 0:
            return (rub / usdt_rate).quantize(Decimal('0.01'))
        return None

    pending_profile    = ProfileChangeRequest.objects.filter(status=ProfileChangeRequest.Status.PENDING).count()
    pending_withdrawal = Withdrawal.objects.filter(status=Withdrawal.Status.PENDING).count()

    recent_payments = list(
        Payment.objects.filter(status=Payment.Status.SUCCESS)
        .select_related('manager')
        .order_by('-created_at')[:10]
    )

    return {
        'managers':           managers,
        'pay_today_sum':      pay_today['s'] or Decimal('0'),
        'pay_today_count':    pay_today['c'] or 0,
        'pay_month_sum':      pay_month['s'] or Decimal('0'),
        'pay_month_count':    pay_month['c'] or 0,
        'pending_profile':    pending_profile,
        'pending_withdrawal': pending_withdrawal,
        'pending_total':      pending_profile + pending_withdrawal,
        'profit_today':       profit_today,
        'profit_today_usdt':  to_usdt(profit_today),
        'profit_week':        profit_week,
        'profit_week_usdt':   to_usdt(profit_week),
        'profit_month':       profit_month,
        'profit_month_usdt':  to_usdt(profit_month),
        'dyn_today':          _dynamics(profit_today, profit_yesterday),
        'dyn_week':           _dynamics(profit_week, profit_prev_week),
        'dyn_month':          _dynamics(profit_month, profit_prev_month),
        'usdt_rate':          usdt_rate,
        'recent_payments':    recent_payments,
        # legacy keys used by get_app_list badges
        'admin_profit_today': profit_today,
    }


# app_label → model object_name (lower) → ключ в stats
_BADGE_MAP = {
    ('payments', 'withdrawal'):              'pending_withdrawal',
    ('managers', 'profilechangerequest'):    'pending_profile',
}


def _get_badge_counts():
    from managers.models import ProfileChangeRequest
    from payments.models import Withdrawal
    return {
        'pending_withdrawal': Withdrawal.objects.filter(status=Withdrawal.Status.PENDING).count(),
        'pending_profile':    ProfileChangeRequest.objects.filter(status=ProfileChangeRequest.Status.PENDING).count(),
    }


class KinexAdminSite(admin.AdminSite):
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['dashboard_stats'] = _get_dashboard_stats()
        return super().index(request, extra_context)

    def get_app_list(self, request, _app_label=None):  # type: ignore[override]
        _APP_ORDER = ['managers', 'payments', 'core']

        app_list = super().get_app_list(request)
        stats = _get_badge_counts()

        for app in app_list:
            for model in app['models']:
                key = (app['app_label'], model['object_name'].lower())
                stat_key = _BADGE_MAP.get(key)
                if stat_key is not None:
                    count = stats[stat_key]
                    suffix = f' ({count})' if count else ' (0)'
                    model['name'] = model['name'] + suffix

        app_list.sort(key=lambda a: (
            _APP_ORDER.index(a['app_label'])
            if a['app_label'] in _APP_ORDER
            else len(_APP_ORDER)
        ))
        return app_list


admin.site.__class__ = KinexAdminSite


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    fields = ('admin_telegram_username', 'bot_id', 'payment_system_commission')

    def has_add_permission(self, request):
        return not Settings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
