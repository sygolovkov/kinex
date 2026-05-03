from django.db import migrations, models


def split_telegram_id(apps, schema_editor):
    Manager = apps.get_model('managers', 'Manager')
    for manager in Manager.objects.all():
        try:
            int(manager.telegram_id)
        except (ValueError, TypeError):
            manager.telegram_username = manager.telegram_id.lstrip('@')
            manager.telegram_id = ''
            manager.save()


class Migration(migrations.Migration):

    dependencies = [
        ('managers', '0002_manager_usdt_wallet'),
    ]

    operations = [
        migrations.AddField(
            model_name='manager',
            name='telegram_username',
            field=models.CharField(blank=True, max_length=64, verbose_name='Telegram username'),
        ),
        migrations.AlterField(
            model_name='manager',
            name='telegram_id',
            field=models.CharField(blank=True, max_length=32, verbose_name='Telegram ID'),
        ),
        migrations.RunPython(split_telegram_id, migrations.RunPython.noop),
    ]
