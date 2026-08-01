from django.db import models
from django.conf import settings


class UserPreference(models.Model):
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
    ]
    LANG_CHOICES = [
        ('en', 'English'),
        ('hi', 'हिन्दी'),
        ('es', 'Español'),
        ('fr', 'Français'),
        ('de', 'Deutsch'),
    ]
    FONT_CHOICES = [
        ('default', 'Default'),
        ('serif', 'Serif'),
        ('mono', 'Monospace'),
        ('rounded', 'Rounded'),
    ]
    ACCENT_CHOICES = [
        ('orange', 'Orange'),
        ('teal', 'Teal'),
        ('blue', 'Blue'),
        ('purple', 'Purple'),
        ('green', 'Green'),
        ('rose', 'Rose'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preference',
    )
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')
    language = models.CharField(max_length=10, choices=LANG_CHOICES, default='en')
    currency = models.CharField(max_length=3, default='USD')
    font_style = models.CharField(max_length=10, choices=FONT_CHOICES, default='default')
    accent = models.CharField(max_length=10, choices=ACCENT_CHOICES, default='orange')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} preferences'
