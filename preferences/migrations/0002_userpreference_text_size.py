from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('preferences', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='userpreference',
            name='text_size',
            field=models.CharField(
                choices=[
                    ('small', 'Small'),
                    ('regular', 'Regular'),
                    ('large', 'Large'),
                    ('xl', 'Extra Large'),
                ],
                default='regular',
                max_length=10,
            ),
        ),
    ]
