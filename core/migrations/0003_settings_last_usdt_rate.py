from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_settings_payment_commission'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='last_usdt_rate',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True, verbose_name='Последний известный курс USDT'),
        ),
    ]
