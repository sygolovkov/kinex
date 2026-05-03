from django.urls import path
from .views import PaymentCallbackView, PaymentCreateView

urlpatterns = [
    path('create', PaymentCreateView.as_view(), name='payment-create'),
    path('callback', PaymentCallbackView.as_view(), name='payment-callback'),
]
