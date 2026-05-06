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


class ProfileChangeRequest(models.Model):
    class Status(models.IntegerChoices):
        PENDING = 0, 'Ожидает обработки'
        COMPLETED = 1, 'Выполнена'

    class Field(models.TextChoices):
        EMAIL = 'email', 'Email'
        USDT_WALLET = 'usdt_wallet', 'USDT кошелёк'

    manager = models.ForeignKey(
        Manager, on_delete=models.CASCADE, related_name='change_requests',
        verbose_name='Менеджер')
    field = models.CharField(
        max_length=20, choices=Field.choices, verbose_name='Поле')
    new_value = models.CharField(
        max_length=255, verbose_name='Новое значение')
    status = models.IntegerField(
        choices=Status.choices, default=Status.PENDING, verbose_name='Статус')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Дата обновления')

    _FIELD_LABELS: dict[str, str] = {'email': 'Email', 'usdt_wallet': 'USDT кошелёк'}
    _STATUS_LABELS: dict[int, str] = {0: 'Ожидает обработки', 1: 'Выполнена'}

    class Meta:
        verbose_name = 'Заявка на изменение профиля'
        verbose_name_plural = 'Заявки на изменение профиля'
        ordering = ('-created_at',)

    def __str__(self):
        field_label = self._FIELD_LABELS.get(self.field, self.field)
        status_label = self._STATUS_LABELS.get(self.status, str(self.status))
        return f'{self.manager} — {field_label} ({status_label})'
