import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('managers', '0003_split_telegram_fields'),
        ('payments', '0003_payment_order_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='is_settled',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Погашен'),
        ),
        migrations.CreateModel(
            name='Withdrawal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12, verbose_name='Сумма')),
                ('status', models.IntegerField(choices=[(0, 'Ожидает обработки'), (1, 'Выполнен')], default=0, verbose_name='Статус')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='withdrawals', to='managers.manager', verbose_name='Менеджер')),
            ],
            options={
                'verbose_name': 'Заявка на вывод',
                'verbose_name_plural': 'Заявки на вывод',
                'ordering': ('-created_at',),
            },
        ),
    ]
