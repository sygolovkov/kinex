from django.db import models
from managers.models import Manager


class Payment(models.Model):
    class Status(models.IntegerChoices):
        CREATED = 0, 'Создан'
        IN_PROCESS = 1, 'В процессе'
        SUCCESS = 2, 'Успешно'
        ERROR = 6, 'Ошибка'
        SERVER_ERROR = -6, 'Ошибка сервера'

    manager = models.ForeignKey(
        Manager, on_delete=models.PROTECT, related_name='payments',
        verbose_name='Менеджер', null=True, blank=True)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Сумма')
    currency = models.CharField(
        max_length=10, default='RUB', verbose_name='Валюта')
    order_id = models.CharField(
        max_length=32, blank=True, unique=True, verbose_name='ID заказа')
    description = models.TextField(blank=True, verbose_name='Описание')
    transaction_id = models.CharField(
        max_length=64, blank=True, verbose_name='ID транзакции')
    status = models.IntegerField(
        choices=Status.choices, default=Status.CREATED, verbose_name='Статус')
    is_settled = models.BooleanField(
        default=False, db_index=True, verbose_name='Погашен')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Платёж'
        verbose_name_plural = 'Платежи'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.manager} — {self.amount} {self.currency} ({self.Status(self.status).label})'


class Withdrawal(models.Model):
    class Status(models.IntegerChoices):
        PENDING = 0, 'Ожидает обработки'
        COMPLETED = 1, 'Выполнен'

    manager = models.ForeignKey(
        Manager, on_delete=models.PROTECT, related_name='withdrawals',
        verbose_name='Менеджер')
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='Сумма')
    status = models.IntegerField(
        choices=Status.choices, default=Status.PENDING, verbose_name='Статус')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Заявка на вывод'
        verbose_name_plural = 'Заявки на вывод'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.manager} — {self.amount} RUB ({self.Status(self.status).label})'
