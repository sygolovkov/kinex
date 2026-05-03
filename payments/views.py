import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone

import requests as http_client
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Payment


@method_decorator(csrf_exempt, name='dispatch')
class PaymentCreateView(View):

    def post(self, request):
        data = json.loads(request.body)
        amount = str(float(data['amount']))
        description = data.get('description', '')

        order_id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc).strftime(
            '%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        body = {
            'merchant': os.environ['PAYMENT_MERCHANT'],
            'order_id': order_id,
            'amount': amount,
            'currency': 'RUB',
            'payment_method': 'sbp',
            'timestamp': timestamp,
            'callback_url': os.environ['PAYMENT_CALLBACK_URL'],
            'success_url': os.environ['PAYMENT_SUCCESS_URL'],
            'fail_url': os.environ['PAYMENT_FAIL_URL'],
        }

        sign_str = ''.join(f'{k}{v}' for k, v in body.items())
        body['sign'] = hmac.new(
            os.environ['PAYMENT_API_KEY'].encode(),
            sign_str.encode(),
            hashlib.sha1,
        ).hexdigest()

        response = http_client.post(
            f'{os.environ['PAYMENT_API_TEST_URL']}/payment',
            data=body,
            timeout=30,
        )
        response_data = response.json()

        Payment.objects.create(
            amount=amount,
            currency='RUB',
            description=description,
            status=response_data.get(
                'status_code', Payment.Status.SERVER_ERROR),
        )

        return JsonResponse(response_data, status=response.status_code)
