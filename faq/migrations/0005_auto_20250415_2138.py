# Generated by Django 3.1.12 on 2025-04-15 21:38

import ckeditor.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('faq', '0004_story'),
    ]

    operations = [
        migrations.AlterField(
            model_name='story',
            name='description',
            field=ckeditor.fields.RichTextField(),
        ),
    ]
