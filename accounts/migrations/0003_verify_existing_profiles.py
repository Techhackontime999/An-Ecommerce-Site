from django.db import migrations


def mark_existing_profiles_verified(apps, schema_editor):
    SellerProfile = apps.get_model('accounts', 'SellerProfile')
    CustomerProfile = apps.get_model('accounts', 'CustomerProfile')
    SellerProfile.objects.update(is_email_verified=True, is_phone_verified=True)
    CustomerProfile.objects.update(is_email_verified=True, is_phone_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_customerprofile_is_email_verified_and_more'),
    ]

    operations = [
        migrations.RunPython(mark_existing_profiles_verified, migrations.RunPython.noop),
    ]
