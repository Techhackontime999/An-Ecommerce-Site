# Generated by Django 3.1.12 on 2025-04-16 10:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderitem',
            name='deal_applied',
            field=models.BooleanField(default=False),
        ),
    ]
