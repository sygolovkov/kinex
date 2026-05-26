from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_order_id_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='withdrawal',
            name='usdt_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Сумма USDT'),
        ),
        migrations.AddField(
            model_name='withdrawal',
            name='usdt_rate',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True, verbose_name='Курс USDT на момент выплаты'),
        ),
        migrations.AlterField(
            model_name='withdrawal',
            name='amount',
            field=models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Сумма RUB'),
        ),
    ]
