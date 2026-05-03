import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone

import requests as http_client

from core.models import get_bot_token
from .models import Payment


def create_payment(amount: float, description: str, manager) -> dict:
    if not description:
        description = f'Платёж {datetime.now().strftime("%d.%m.%Y %H:%M")}'

    order_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

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
            amount=amount,
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
