# Generated by Django 3.1.12 on 2025-04-19 02:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0004_auto_20250416_0210'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerprofile',
            name='bank_account',
            field=models.CharField(default=1, max_length=100),
        ),
    ]
