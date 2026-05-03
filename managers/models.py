from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models


class Manager(models.Model):
    telegram_id = models.CharField(max_length=32, blank=True, verbose_name='Telegram ID')
    telegram_username = models.CharField(max_length=64, blank=True, verbose_name='Telegram username')
    name = models.CharField(max_length=255, blank=True, verbose_name='Имя')
    email = models.EmailField(blank=True, verbose_name='Email')
    usdt_wallet = models.CharField(max_length=128, blank=True, verbose_name='USDT кошелёк')
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('5.00'), verbose_name='Комиссия (%)')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    def clean(self):
        if not self.telegram_id and not self.telegram_username:
            raise ValidationError('Укажите Telegram ID или username.')
        qs = Manager.objects.exclude(pk=self.pk)
        if self.telegram_id and qs.filter(telegram_id=self.telegram_id).exists():
            raise ValidationError({'telegram_id': 'Менеджер с таким Telegram ID уже существует.'})
        if self.telegram_username and qs.filter(telegram_username=self.telegram_username).exists():
            raise ValidationError({'telegram_username': 'Менеджер с таким username уже существует.'})

    class Meta:
        verbose_name = 'Менеджер'
        verbose_name_plural = 'Менеджеры'

    def __str__(self):
        return self.name or self.telegram_username or self.telegram_id or f'Менеджер #{self.pk}'
