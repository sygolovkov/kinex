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


def _get_dashboard_stats():
    from managers.models import Manager, ProfileChangeRequest
    from payments.models import Payment, Withdrawal

    now = timezone.localtime()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = today.replace(day=1)

    managers = Manager.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
    )

    def pay_agg(qs):
        return qs.filter(status=Payment.Status.SUCCESS).aggregate(
            s=Sum('amount'), c=Count('id'),
        )

    pay_all = pay_agg(Payment.objects)
    pay_today = pay_agg(Payment.objects.filter(created_at__gte=today))
    pay_month = pay_agg(Payment.objects.filter(created_at__gte=month_start))

    admin_profit_today = Payment.objects.filter(
        status=Payment.Status.SUCCESS,
        created_at__gte=today,
        manager__isnull=False,
    ).annotate(
        commission_amount=ExpressionWrapper(
            F('amount') * F('manager__commission') / 100,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).aggregate(total=Sum('commission_amount'))['total'] or Decimal('0')

    status_map = {
        r['status']: r['cnt']
        for r in Payment.objects.values('status').annotate(cnt=Count('id'))
    }

    pending_profile = ProfileChangeRequest.objects.filter(
        status=ProfileChangeRequest.Status.PENDING).count()
    pending_withdrawal = Withdrawal.objects.filter(
        status=Withdrawal.Status.PENDING).count()

    withdrawn_month = Withdrawal.objects.filter(
        status=Withdrawal.Status.COMPLETED,
        created_at__gte=month_start,
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    return {
        'managers': managers,
        'pay_all_sum':        pay_all['s']   or Decimal('0'),
        'pay_all_count':      pay_all['c']   or 0,
        'pay_today_sum':      pay_today['s'] or Decimal('0'),
        'pay_today_count':    pay_today['c'] or 0,
        'pay_month_sum':      pay_month['s'] or Decimal('0'),
        'pay_month_count':    pay_month['c'] or 0,
        'pay_in_process':     status_map.get(1, 0),
        'pay_error':          status_map.get(6, 0),
        'pending_profile':    pending_profile,
        'pending_withdrawal': pending_withdrawal,
        'pending_total':      pending_profile + pending_withdrawal,
        'withdrawn_month':    withdrawn_month,
        'admin_profit_today': admin_profit_today.quantize(Decimal('0.01')),
    }


# app_label → model object_name (lower) → ключ в stats
_BADGE_MAP = {
    ('payments', 'withdrawal'):              'pending_withdrawal',
    ('managers', 'profilechangerequest'):    'pending_profile',
}


class KinexAdminSite(admin.AdminSite):
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['dashboard_stats'] = _get_dashboard_stats()
        return super().index(request, extra_context)

    def get_app_list(self, request, _app_label=None):  # type: ignore[override]
        _APP_ORDER = ['managers', 'payments', 'core']

        app_list = super().get_app_list(request)
        stats = _get_dashboard_stats()

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
