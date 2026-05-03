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
    description = models.TextField(blank=True, verbose_name='Описание')
    transaction_id = models.CharField(
        max_length=64, blank=True, verbose_name='ID транзакции')
    status = models.IntegerField(
        choices=Status.choices, default=Status.CREATED, verbose_name='Статус')
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
