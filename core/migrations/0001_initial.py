from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Settings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('admin_telegram_username', models.CharField(blank=True, max_length=64, verbose_name='Telegram username администратора')),
                ('bot_id', models.CharField(blank=True, max_length=128, verbose_name='Bot Token')),
            ],
            options={
                'verbose_name': 'Настройки',
                'verbose_name_plural': 'Настройки',
            },
        ),
    ]
