from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_payment_transaction_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='order_id',
            field=models.CharField(blank=True, db_index=True, max_length=32, verbose_name='ID заказа'),
        ),
    ]
