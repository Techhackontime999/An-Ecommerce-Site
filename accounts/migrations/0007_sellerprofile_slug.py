# Generated by Django 3.1.12 on 2025-04-19 05:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_auto_20250419_0259'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerprofile',
            name='slug',
            field=models.SlugField(blank=True, null=True),
        ),
    ]
