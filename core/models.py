import os

from django.db import models


class Settings(models.Model):
    admin_telegram_username = models.CharField(
        max_length=64, blank=True, verbose_name='Telegram username администратора')
    bot_id = models.CharField(
        max_length=128, blank=True, verbose_name='Bot Token')

    class Meta:
        verbose_name = 'Настройки'
        verbose_name_plural = 'Настройки'

    def __str__(self):
        return 'Настройки приложения'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def get_bot_token() -> str:
    try:
        token = Settings.get().bot_id
        if token:
            return token
    except Exception:
        pass
    return os.environ['BOT_TOKEN']
