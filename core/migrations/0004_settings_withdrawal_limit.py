from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_settings_last_usdt_rate'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='withdrawal_limit',
            field=models.DecimalField(decimal_places=2, default=Decimal('400000.00'), max_digits=12, verbose_name='Лимит накоплений (RUB)'),
        ),
    ]
