from django.db import models


class SiteSetting(models.Model):
    """A single site-wide configuration value editable from Platform Studio.

    ``value`` is stored as text. Boolean settings use ``'0'`` / ``'1'`` so
    templates can compare against ``'1'`` directly. When no row exists the
    schema default in ``settings_definitions.py`` applies, so the site keeps
    working even before any row is created.
    """

    key = models.SlugField(max_length=100, unique=True)
    label = models.CharField(max_length=120)
    value = models.TextField(blank=True, default='')
    group = models.CharField(max_length=50, db_index=True)
    field_type = models.CharField(
        max_length=20,
        default='text',
        choices=[
            ('text', 'Text'),
            ('textarea', 'Text area'),
            ('boolean', 'Boolean'),
            ('select', 'Select'),
            ('color', 'Color'),
            ('number', 'Number'),
        ],
    )
    help_text = models.TextField(blank=True, default='')
    ordering = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['group', 'ordering', 'key']
        verbose_name = 'Site Setting'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f'{self.label} ({self.key})'
