# Generated by Django 3.1.12 on 2025-04-15 18:38

import ckeditor.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('faq', '0002_auto_20250415_1824'),
    ]

    operations = [
        migrations.AlterField(
            model_name='faq',
            name='answer',
            field=ckeditor.fields.RichTextField(),
        ),
    ]
