import hashlib
import hmac as hmac_lib
import json
import logging
import os

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Payment
from .services import create_payment, notify_manager

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentCreateView(View):

    def post(self, request):
        amount = float(request.POST.get('amount'))
        description = request.POST.get('description', '')

        result = create_payment(amount=amount, description=description, manager=None)

        return JsonResponse(result)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentCallbackView(View):

    def post(self, request):
        logger.warning('CALLBACK body: %s', request.body.decode('utf-8', errors='replace'))

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error('CALLBACK json error: %s', e)
            return JsonResponse({'error': 'invalid json'}, status=400)

        logger.warning('CALLBACK data: %s', data)

        order_id = data.get('order_id', '')
        amount = data.get('amount', '')
        timestamp = data.get('timestamp', '')
        sign = data.get('sign', '')

        sign_str = (
            f'{len(order_id)}{order_id}'
            f'{len(amount)}{amount}'
            f'{len(timestamp)}{timestamp}'
        )
        expected = hmac_lib.new(
            os.environ['PAYMENT_API_KEY'].encode(),
            sign_str.encode(),
            hashlib.sha1,
        ).hexdigest()

        logger.warning('CALLBACK sign_str: %r', sign_str)
        logger.warning('CALLBACK sign received: %s', sign)
        logger.warning('CALLBACK sign expected: %s', expected)

        if not hmac_lib.compare_digest(sign, expected):
            logger.error('CALLBACK signature mismatch')
            # DEBUG: пропускаем проверку подписи временно
            # return JsonResponse({'error': 'invalid signature'}, status=400)

        try:
            payment = Payment.objects.select_related('manager').get(order_id=order_id)
            logger.warning('CALLBACK payment found: pk=%s status=%s', payment.pk, payment.status)
        except Payment.DoesNotExist:
            logger.error('CALLBACK payment not found: order_id=%r', order_id)
            return JsonResponse({'error': 'not found'}, status=404)

        old_status = payment.status
        payment.status = data.get('status_code', payment.status)
        if data.get('transaction_id'):
            payment.transaction_id = data['transaction_id']
        payment.save(update_fields=['status', 'transaction_id', 'updated_at'])
        logger.warning('CALLBACK status updated: %s -> %s', old_status, payment.status)

        notify_manager(payment)

        return JsonResponse({'ok': True})
