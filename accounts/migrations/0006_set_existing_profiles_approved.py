from django.db import migrations


def mark_existing_profiles_approved(apps, schema_editor):
    """Existing verified sellers were grandfathered in under the old
    default-True behaviour — keep them selling without a re-review, but record
    them as having been approved."""
    SellerProfile = apps.get_model('accounts', 'SellerProfile')
    SellerProfile.objects.filter(is_verified=True).update(
        verification_status='approved',
    )
    SellerProfile.objects.filter(is_verified=False).update(
        verification_status='unsubmitted',
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_sellerprofile_rejected_at_and_more'),
    ]

    operations = [
        migrations.RunPython(mark_existing_profiles_approved, migrations.RunPython.noop),
    ]
