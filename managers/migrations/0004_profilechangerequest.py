import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('managers', '0003_split_telegram_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProfileChangeRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('field', models.CharField(choices=[('email', 'Email'), ('usdt_wallet', 'USDT кошелёк')], max_length=20, verbose_name='Поле')),
                ('new_value', models.CharField(max_length=255, verbose_name='Новое значение')),
                ('status', models.IntegerField(choices=[(0, 'Ожидает обработки'), (1, 'Выполнена')], default=0, verbose_name='Статус')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
                ('manager', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='change_requests', to='managers.manager', verbose_name='Менеджер')),
            ],
            options={
                'verbose_name': 'Заявка на изменение профиля',
                'verbose_name_plural': 'Заявки на изменение профиля',
                'ordering': ('-created_at',),
            },
        ),
    ]
