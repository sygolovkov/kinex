import hashlib
import hmac as hmac_lib
import json
import os

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Payment
from .services import notify_manager


@method_decorator(csrf_exempt, name='dispatch')
class PaymentCallbackView(View):

    def post(self, request):
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'error': 'invalid json'}, status=400)

        order_id = str(data.get('order_id', ''))
        amount = str(data.get('amount', ''))
        timestamp = str(data.get('timestamp', ''))
        sign = str(data.get('sign', ''))

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

        if not hmac_lib.compare_digest(sign, expected):
            return JsonResponse({'error': 'invalid signature'}, status=400)

        try:
            payment = Payment.objects.select_related('manager').get(order_id=order_id)
        except Payment.DoesNotExist:
            return JsonResponse({'error': 'not found'}, status=404)

        payment.status = data.get('status_code', payment.status)
        if data.get('transaction_id'):
            payment.transaction_id = data['transaction_id']
        payment.save(update_fields=['status', 'transaction_id', 'updated_at'])

        notify_manager(payment)

        return JsonResponse({'ok': True})
