from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reviews', '0005_delete_review'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productreview',
            name='status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                db_index=True,
                default='pending',
                help_text='New reviews start pending admin moderation; only approved reviews are public.',
                max_length=10,
            ),
        ),
    ]
