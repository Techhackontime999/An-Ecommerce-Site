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
        ('pt', 'Português'),
        ('it', 'Italiano'),
        ('ja', '日本語'),
        ('ko', '한국어'),
        ('zh-hans', '简体中文'),
        ('ar', 'العربية'),
        ('ru', 'Русский'),
        ('tr', 'Türkçe'),
        ('nl', 'Nederlands'),
        ('pl', 'Polski'),
        ('bn', 'বাংলা'),
        ('ta', 'தமிழ்'),
        ('te', 'తెలుగు'),
        ('mr', 'मराठी'),
    ]
    FONT_CHOICES = [
        ('default', 'Default'),
        ('serif', 'Serif'),
        ('mono', 'Monospace'),
        ('rounded', 'Rounded'),
        ('elegant', 'Elegant'),
        ('playful', 'Playful'),
        ('hand', 'Handwritten'),
    ]
    ACCENT_CHOICES = [
        ('orange', 'Orange'),
        ('teal', 'Teal'),
        ('blue', 'Blue'),
        ('purple', 'Purple'),
        ('green', 'Green'),
        ('rose', 'Rose'),
        ('indigo', 'Indigo'),
        ('cyan', 'Cyan'),
        ('amber', 'Amber'),
        ('pink', 'Pink'),
        ('lime', 'Lime'),
        ('gold', 'Gold'),
    ]
    TEXT_SIZE_CHOICES = [
        ('small', 'Small'),
        ('regular', 'Regular'),
        ('large', 'Large'),
        ('xl', 'Extra Large'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preference',
    )
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='light')
    language = models.CharField(max_length=10, choices=LANG_CHOICES, default='en')
    currency = models.CharField(max_length=3, default='INR')
    font_style = models.CharField(max_length=10, choices=FONT_CHOICES, default='default')
    accent = models.CharField(max_length=10, choices=ACCENT_CHOICES, default='orange')
    text_size = models.CharField(max_length=10, choices=TEXT_SIZE_CHOICES, default='regular')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} preferences'
