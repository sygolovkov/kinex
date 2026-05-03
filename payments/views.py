from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .services import create_payment


@method_decorator(csrf_exempt, name='dispatch')
class PaymentCreateView(View):

    def post(self, request):
        amount = float(request.POST.get('amount'))
        description = request.POST.get('description', '')

        result = create_payment(amount=amount, description=description, manager=None)

        return JsonResponse(result)
