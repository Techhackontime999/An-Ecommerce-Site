"""Encrypt any legacy plaintext courier credentials already in the database.

Fernet is non-deterministic, so this must run once to convert existing values;
new values are encrypted automatically by the field on save.
"""

from django.db import migrations


def encrypt_existing(apps, schema_editor):
    CourierCompany = apps.get_model('logistics', 'CourierCompany')
    for company in CourierCompany.objects.all().iterator():
        changed = False
        if company.api_key:
            company.api_key = company.api_key
            changed = True
        if company.api_secret:
            company.api_secret = company.api_secret
            changed = True
        if changed:
            company.save(update_fields=['api_key', 'api_secret', 'updated_at'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('logistics', '0005_alter_couriercompany_api_key_and_more'),
    ]

    operations = [
        migrations.RunPython(encrypt_existing, noop),
    ]
