from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='transaction_id',
            field=models.CharField(blank=True, max_length=64, verbose_name='ID транзакции'),
        ),
    ]
