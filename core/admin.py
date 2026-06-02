import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import admin
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import ExtractHour
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
        status__in=[2],  # Payment.Status.SUCCESS = 2
        manager__isnull=False,
    ).annotate(
        ca=ExpressionWrapper(
            F('amount') * F('manager__commission') / 100,
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).aggregate(total=Sum('ca'))['total']
    return (result or Decimal('0')).quantize(Decimal('0.01'))


def _dynamics(current, previous):
    """Возвращает процент изменения или None если нет данных за предыдущий период."""
    if previous and previous > 0:
        return round(float((current - previous) / previous * 100), 1)
    return None


def _get_dashboard_stats():
    from managers.models import Manager, ProfileChangeRequest
    from payments.models import Payment, Withdrawal
    from payments.services import get_usdt_rate

    now        = timezone.localtime()
    today      = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday  = today - timedelta(days=1)
    week_start = today - timedelta(days=7)
    prev_week_start = today - timedelta(days=14)
    month_start = today.replace(day=1)
    if today.month == 1:
        prev_month_start = today.replace(year=today.year - 1, month=12, day=1)
    else:
        prev_month_start = today.replace(month=today.month - 1, day=1)

    # ── Менеджеры ──
    managers = Manager.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(is_active=True)),
        inactive=Count('id', filter=Q(is_active=False)),
    )

    # ── Успешные платежи (сегодня / вчера / месяц) ──
    def pay_agg(qs):
        return qs.filter(status=Payment.Status.SUCCESS).aggregate(
            s=Sum('amount'), c=Count('id'),
        )

    pay_today     = pay_agg(Payment.objects.filter(created_at__gte=today))
    pay_yesterday = pay_agg(Payment.objects.filter(created_at__gte=yesterday, created_at__lt=today))
    pay_month     = pay_agg(Payment.objects.filter(created_at__gte=month_start))

    # ── Прибыль ──
    p = Payment.objects
    profit_today      = _calc_profit(p.filter(created_at__gte=today))
    profit_yesterday  = _calc_profit(p.filter(created_at__gte=yesterday, created_at__lt=today))
    profit_week       = _calc_profit(p.filter(created_at__gte=week_start))
    profit_prev_week  = _calc_profit(p.filter(created_at__gte=prev_week_start, created_at__lt=week_start))
    profit_month      = _calc_profit(p.filter(created_at__gte=month_start))
    profit_prev_month = _calc_profit(p.filter(created_at__gte=prev_month_start, created_at__lt=month_start))

    # ── Все транзакции сегодня / вчера (любой статус) ──
    all_today     = Payment.objects.filter(created_at__gte=today).aggregate(c=Count('id'))['c'] or 0
    all_yesterday = Payment.objects.filter(created_at__gte=yesterday, created_at__lt=today).aggregate(c=Count('id'))['c'] or 0

    # ── Активные (IN_PROCESS) ──
    active_now  = Payment.objects.filter(status=Payment.Status.IN_PROCESS).count()
    active_prev = Payment.objects.filter(
        status=Payment.Status.IN_PROCESS,
        created_at__gte=yesterday, created_at__lt=today,
    ).count()

    # ── Почасовые данные для графика (успешные платежи по часам, московское время) ──
    tz_info = timezone.get_current_timezone()
    hourly_raw = (
        Payment.objects
        .filter(created_at__gte=today, status=Payment.Status.SUCCESS)
        .annotate(hour=ExtractHour('created_at', tzinfo=tz_info))
        .values('hour')
        .annotate(cnt=Count('id'))
        .order_by('hour')
    )
    by_hour = {row['hour']: row['cnt'] for row in hourly_raw}
    hourly_data   = [by_hour.get(h, 0) for h in range(24)]
    hourly_labels = [f'{h:02d}:00' for h in range(24)]

    # ── USDT ──
    usdt_rate = get_usdt_rate()

    def to_usdt(rub):
        if usdt_rate > 0:
            return (rub / usdt_rate).quantize(Decimal('0.01'))
        return Decimal('0')

    # ── Настройки (лимит, комиссия ПС) ──
    settings_obj      = Settings.get()
    ps_rate_decimal   = settings_obj.payment_system_commission / Decimal('100')
    withdrawal_limit  = settings_obj.withdrawal_limit or Decimal('400000.00')

    # ── Общий баланс (все успешные платежи) ──
    total_gross = Payment.objects.filter(
        status=Payment.Status.SUCCESS,
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # ── Доступно к выводу: непогашенные SUCCESS-платежи до сегодня, нетто ──
    available_raw = Payment.objects.filter(
        status=Payment.Status.SUCCESS,
        is_settled=False,
        created_at__lt=today,
        manager__isnull=False,
    ).annotate(
        net=ExpressionWrapper(
            F('amount') * (Decimal('1') - ps_rate_decimal)
            - F('amount') * F('manager__commission') / Decimal('100'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).aggregate(total=Sum('net'))['total']
    available_total = (available_raw or Decimal('0')).quantize(Decimal('0.01'))

    limit_progress = round(
        min(float(available_total / withdrawal_limit * 100), 100), 1
    ) if withdrawal_limit > 0 else 0.0

    # ── Ожидают обработки (счётчики для тайлов) ──
    pending_profile    = ProfileChangeRequest.objects.filter(status=ProfileChangeRequest.Status.PENDING).count()
    pending_withdrawal = Withdrawal.objects.filter(status=Withdrawal.Status.PENDING).count()

    # ── Необработанные заявки (списки для таблицы) ──
    pending_withdrawals_list = list(
        Withdrawal.objects.filter(status=Withdrawal.Status.PENDING)
        .select_related('manager')
        .order_by('-created_at')
    )
    pending_profile_list = list(
        ProfileChangeRequest.objects.filter(status=ProfileChangeRequest.Status.PENDING)
        .select_related('manager')
        .order_by('-created_at')
    )

    # ── Последние 10 платежей (все статусы) ──
    recent_payments = list(
        Payment.objects.select_related('manager').order_by('-created_at')[:10]
    )

    return {
        # Tiles
        'managers':           managers,
        'pay_today_sum':      pay_today['s']     or Decimal('0'),
        'pay_today_count':    pay_today['c']     or 0,
        'pay_month_sum':      pay_month['s']     or Decimal('0'),
        'pay_month_count':    pay_month['c']     or 0,
        'dyn_pay_count':      _dynamics(pay_today['c'] or 0,             pay_yesterday['c'] or 0),
        'dyn_pay_sum':        _dynamics(pay_today['s'] or Decimal('0'),  pay_yesterday['s'] or Decimal('0')),
        'pending_profile':    pending_profile,
        'pending_withdrawal': pending_withdrawal,
        'pending_total':      pending_profile + pending_withdrawal,
        # Прибыль
        'profit_today':       profit_today,
        'profit_today_usdt':  to_usdt(profit_today),
        'profit_week':        profit_week,
        'profit_week_usdt':   to_usdt(profit_week),
        'profit_month':       profit_month,
        'profit_month_usdt':  to_usdt(profit_month),
        'dyn_today':          _dynamics(profit_today,  profit_yesterday),
        'dyn_week':           _dynamics(profit_week,   profit_prev_week),
        'dyn_month':          _dynamics(profit_month,  profit_prev_month),
        'usdt_rate':          usdt_rate,
        # Сегодня
        'all_today_count':    all_today,
        'dyn_all_count':      _dynamics(all_today,   all_yesterday),
        'active_count':       active_now,
        'dyn_active':         _dynamics(active_now,  active_prev),
        # Chart
        'hourly_labels_json': json.dumps(hourly_labels),
        'hourly_data_json':   json.dumps(hourly_data),
        # Баланс
        'total_gross':            total_gross,
        'total_gross_usdt':       to_usdt(total_gross),
        'available_total':        available_total,
        'available_total_usdt':   to_usdt(available_total),
        'withdrawal_limit':       withdrawal_limit,
        'limit_progress':         limit_progress,
        # Заявки
        'pending_withdrawals_list': pending_withdrawals_list,
        'pending_profile_list':     pending_profile_list,
        # Последние платежи
        'recent_payments':    recent_payments,
        # legacy
        'admin_profit_today': profit_today,
    }


class KinexAdminSite(admin.AdminSite):
    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['dashboard_stats'] = _get_dashboard_stats()
        return super().index(request, extra_context)

    def get_app_list(self, request, _app_label=None):  # type: ignore[override]
        _APP_ORDER = ['managers', 'payments', 'core']
        app_list = super().get_app_list(request)
        app_list.sort(key=lambda a: (
            _APP_ORDER.index(a['app_label'])
            if a['app_label'] in _APP_ORDER
            else len(_APP_ORDER)
        ))
        return app_list


admin.site.__class__ = KinexAdminSite


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    fields = ('admin_telegram_username', 'payment_system_commission', 'withdrawal_limit', 'last_usdt_rate')
    readonly_fields = ('last_usdt_rate',)

    def has_add_permission(self, request):
        return not Settings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
