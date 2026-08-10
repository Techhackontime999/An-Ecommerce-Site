from django.db import migrations, models


def backfill_confirmed(apps, schema_editor):
    """Grandfather existing active subscribers as confirmed (they consented
    before double opt-in existed). Unconfirmed records stay inactive."""
    Subscriber = apps.get_model('newsletter', 'Subscriber')
    Subscriber.objects.filter(is_active=True).update(
        is_confirmed=True, confirmed_at=models.F('created_at'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('newsletter', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscriber',
            name='is_active',
            field=models.BooleanField(default=False, help_text='Only confirmed (double opt-in) subscribers are active.'),
        ),
        migrations.AddField(
            model_name='subscriber',
            name='is_confirmed',
            field=models.BooleanField(default=False, help_text='True once the subscriber clicked the confirmation link in the double opt-in email. The single source of consent.'),
        ),
        migrations.AddField(
            model_name='subscriber',
            name='confirmed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(backfill_confirmed, migrations.RunPython.noop),
    ]
