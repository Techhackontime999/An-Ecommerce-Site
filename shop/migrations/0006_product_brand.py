# Generated by Django 3.1.12 on 2025-04-17 18:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0005_product_seller'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='brand',
            field=models.CharField(default=False, max_length=100),
        ),
    ]
