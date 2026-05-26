import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import requests as http_client
from django.db import transaction
from django.utils import timezone as dj_timezone

from core.models import Settings, get_bot_token
from .models import Payment, Withdrawal

_usdt_cache: dict = {}
_USDT_CACHE_TTL = 900  # 15 минут


def get_usdt_rate() -> Decimal:
    cached_at = _usdt_cache.get('cached_at')
    if cached_at is not None:
        age = datetime.now(timezone.utc).timestamp() - cached_at
        if age < _USDT_CACHE_TTL and _usdt_cache.get('rate', Decimal('0')) > 0:
            return _usdt_cache['rate']
    try:
        resp = http_client.get(
            'https://api.coingecko.com/api/v3/simple/price',
            params={'ids': 'tether', 'vs_currencies': 'rub'},
            timeout=5,
        )
        rate = Decimal(str(resp.json()['tether']['rub']))
    except Exception:
        return _usdt_cache.get('rate', Decimal('0'))
    _usdt_cache['rate'] = rate
    _usdt_cache['cached_at'] = datetime.now(timezone.utc).timestamp()
    return rate


def create_payment(amount: float, description: str, manager) -> dict:
    if not description:
        description = f'Платёж {datetime.now().strftime("%d.%m.%Y %H:%M")}'

    order_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    body = {
        'merchant': os.environ['PAYMENT_MERCHANT'],
        'order_id': order_id,
        'amount': str(float(amount)),
        'currency': 'RUB',
        'payment_method': 'sbp',
        'timestamp': timestamp,
        'callback_url': os.environ['PAYMENT_CALLBACK_URL'],
    }

    sign_str = ''.join(f'{k}{v}' for k, v in body.items())
    body['sign'] = hmac.new(
        os.environ['PAYMENT_API_KEY'].encode(),
        sign_str.encode(),
        hashlib.sha1,
    ).hexdigest()

    response = http_client.post(
        f'{os.environ["PAYMENT_API_TEST_URL"]}/payment',
        data=body,
        timeout=30,
    )
    data = response.json()
    status_code = data.get('status_code', Payment.Status.SERVER_ERROR)

    if status_code != Payment.Status.SERVER_ERROR:
        Payment.objects.create(
            manager=manager,
            order_id=order_id,
            amount=Decimal(str(amount)),
            currency='RUB',
            description=description,
            transaction_id=data.get('transaction_id', ''),
            status=status_code,
        )

    return data


_STATUS_EMOJI = {
    Payment.Status.CREATED: '🆕',
    Payment.Status.IN_PROCESS: '⏳',
    Payment.Status.SUCCESS: '✅',
    Payment.Status.ERROR: '❌',
    Payment.Status.SERVER_ERROR: '⚠️',
}


def _local_midnight():
    return dj_timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)


def get_balance_stats(manager, period: str) -> dict:
    from django.db.models import Sum
    today_midnight = _local_midnight()
    since = today_midnight if period == 'today' else today_midnight.replace(day=1)

    total = Payment.objects.filter(
        manager=manager,
        status=Payment.Status.SUCCESS,
        created_at__gte=since,
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

    settings = Settings.get()
    manager_rate = manager.commission / Decimal('100')
    ps_rate = settings.payment_system_commission / Decimal('100')
    total_rate = manager_rate + ps_rate
    net_rate = Decimal('1') - total_rate

    # Выведено = завершённые заявки, фильтруем по updated_at —
    # дате фактического завершения, а не создания заявки
    withdrawn = Withdrawal.objects.filter(
        manager=manager,
        status=Withdrawal.Status.COMPLETED,
        updated_at__gte=since,
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')

    # Удержано = комиссия только по фактически выведенным средствам
    # withdrawal_amount = gross × net_rate  →  retained = withdrawal × total_rate / net_rate
    retained_fee = (
        (withdrawn * total_rate / net_rate).quantize(Decimal('0.01'))
        if net_rate > Decimal('0') else Decimal('0')
    )

    return {
        'total':        total,
        'retained_fee': retained_fee,
        'withdrawn':    withdrawn,
        'available':    calculate_available_balance(manager, settings),
    }


def calculate_available_balance(manager, settings=None) -> Decimal:
    from django.db.models import Sum
    today_midnight = _local_midnight()
    total = Payment.objects.filter(
        manager=manager,
        status=Payment.Status.SUCCESS,
        is_settled=False,
        created_at__lt=today_midnight,
    ).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    if settings is None:
        settings = Settings.get()
    manager_rate = manager.commission / Decimal('100')
    ps_rate = settings.payment_system_commission / Decimal('100')
    return (total * (Decimal('1') - manager_rate - ps_rate)).quantize(Decimal('0.01'))


@transaction.atomic
def create_withdrawal(manager) -> Withdrawal:
    from django.db.models import Sum
    # select_for_update(of=('self',)) блокирует строки менеджера чтобы
    # исключить гонку при одновременных запросах на вывод
    from managers.models import Manager as ManagerModel
    ManagerModel.objects.select_for_update().get(pk=manager.pk)

    if Withdrawal.objects.filter(
        manager=manager, status=Withdrawal.Status.PENDING,
    ).exists():
        raise ValueError('active_withdrawal_exists')

    today_midnight = _local_midnight()
    payment_qs = Payment.objects.select_for_update().filter(
        manager=manager,
        status=Payment.Status.SUCCESS,
        is_settled=False,
        created_at__lt=today_midnight,
    )
    total = payment_qs.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    settings = Settings.get()
    manager_rate = manager.commission / Decimal('100')
    ps_rate = settings.payment_system_commission / Decimal('100')
    amount = (total * (Decimal('1') - manager_rate - ps_rate)).quantize(Decimal('0.01'))

    if amount <= 0:
        raise ValueError('no_funds_available')

    withdrawal = Withdrawal.objects.create(manager=manager, amount=amount)
    payment_qs.update(is_settled=True)
    return withdrawal


def notify_manager(payment) -> None:
    if not payment.manager:
        return
    try:
        chat_id = int(payment.manager.telegram_id)
    except ValueError:
        return

    emoji = _STATUS_EMOJI.get(payment.status, '❓')
    status_label = Payment.Status(payment.status).label
    text = (
        f'{emoji} Статус платежа обновлён\n\n'
        f'💰 Сумма: {payment.amount} {payment.currency}\n'
        f'📝 Назначение: {payment.description or "—"}\n'
        f'📊 Статус: {status_label}'
    )
    if payment.transaction_id:
        text += f'\n🆔 Транзакция: {payment.transaction_id}'

    try:
        http_client.post(
            f'https://api.telegram.org/bot{get_bot_token()}/sendMessage',
            json={'chat_id': chat_id, 'text': text},
            timeout=5,
        )
    except Exception:
        pass
