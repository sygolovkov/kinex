from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('managers', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='manager',
            name='usdt_wallet',
            field=models.CharField(blank=True, max_length=128, verbose_name='USDT кошелёк'),
        ),
    ]
