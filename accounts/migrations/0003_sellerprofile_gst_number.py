# Generated by Django 3.1.12 on 2025-04-14 20:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_auto_20250414_1924'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerprofile',
            name='gst_number',
            field=models.CharField(blank=True, max_length=15, null=True),
        ),
    ]
