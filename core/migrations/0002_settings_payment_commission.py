from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='settings',
            name='payment_system_commission',
            field=models.DecimalField(decimal_places=2, default='5.00', max_digits=5, verbose_name='Комиссия платёжной системы (%)'),
        ),
    ]
