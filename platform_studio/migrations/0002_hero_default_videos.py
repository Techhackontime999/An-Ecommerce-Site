from django.db import migrations

NEW_DEFAULTS = {
    'hero_video_light': '/static/hero/light_hero.mp4',
    'hero_video_dark': '/static/hero/dark_hero.mp4',
}


def apply_new_defaults(apps, schema_editor):
    SiteSetting = apps.get_model('platform_studio', 'SiteSetting')
    for key, value in NEW_DEFAULTS.items():
        SiteSetting.objects.filter(key=key, value='').update(value=value)


def revert_new_defaults(apps, schema_editor):
    SiteSetting = apps.get_model('platform_studio', 'SiteSetting')
    for key, value in NEW_DEFAULTS.items():
        SiteSetting.objects.filter(key=key, value=value).update(value='')


class Migration(migrations.Migration):

    dependencies = [
        ('platform_studio', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(apply_new_defaults, revert_new_defaults),
    ]