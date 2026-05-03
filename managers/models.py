from decimal import Decimal
from django.db import models


class Manager(models.Model):
    telegram_id = models.CharField(max_length=64, unique=True, verbose_name='Telegram ID')
    name = models.CharField(max_length=255, blank=True, verbose_name='Имя')
    email = models.EmailField(blank=True, verbose_name='Email')
    usdt_wallet = models.CharField(max_length=128, blank=True, verbose_name='USDT кошелёк')
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'), verbose_name='Комиссия (%)')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Менеджер'
        verbose_name_plural = 'Менеджеры'

    def __str__(self):
        return self.telegram_id
