from decimal import Decimal

from django import template
from django.db.models import Count, Q, Sum
from django.utils import timezone

register = template.Library()


@register.simple_tag
def current_usdt_rate():
    from payments.services import get_usdt_rate
    return get_usdt_rate()


@register.simple_tag
def get_admin_stats():
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

    def payment_sum(qs):
        return qs.filter(status=Payment.Status.SUCCESS).aggregate(
            s=Sum('amount'), c=Count('id')
        )

    pay_all = payment_sum(Payment.objects)
    pay_today = payment_sum(Payment.objects.filter(created_at__gte=today))
    pay_month = payment_sum(Payment.objects.filter(created_at__gte=month_start))

    pay_by_status = Payment.objects.values('status').annotate(cnt=Count('id'))
    status_map = {row['status']: row['cnt'] for row in pay_by_status}

    pending_profile = ProfileChangeRequest.objects.filter(
        status=ProfileChangeRequest.Status.PENDING
    ).count()
    pending_withdrawal = Withdrawal.objects.filter(
        status=Withdrawal.Status.PENDING
    ).count()

    completed_withdrawal_month = Withdrawal.objects.filter(
        status=Withdrawal.Status.COMPLETED,
        created_at__gte=month_start,
    ).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    return {
        'managers': managers,
        'pay_all_sum': pay_all['s'] or Decimal('0'),
        'pay_all_count': pay_all['c'] or 0,
        'pay_today_sum': pay_today['s'] or Decimal('0'),
        'pay_today_count': pay_today['c'] or 0,
        'pay_month_sum': pay_month['s'] or Decimal('0'),
        'pay_month_count': pay_month['c'] or 0,
        'pay_in_process': status_map.get(1, 0),
        'pay_error': status_map.get(6, 0),
        'pending_profile': pending_profile,
        'pending_withdrawal': pending_withdrawal,
        'completed_withdrawal_month': completed_withdrawal_month,
        'pending_total': pending_profile + pending_withdrawal,
    }
