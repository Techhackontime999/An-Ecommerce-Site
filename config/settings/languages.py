"""Compute the set of languages actually shipped with compiled catalogs.

The site declares 19 languages, but only the ones with a compiled
``locale/<code>/LC_MESSAGES/django.mo`` file are offered in the language
pickers. ``en`` is always available as the source language.
"""

import os

ALL_LANGUAGES = [
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


def _locale_dir():
    project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_dir, 'locale')


def available_languages():
    locale_dir = _locale_dir()
    languages = []
    for code, name in ALL_LANGUAGES:
        if code == 'en':
            languages.append((code, name))
            continue
        catalog = os.path.join(locale_dir, code, 'LC_MESSAGES', 'django.mo')
        if os.path.exists(catalog):
            languages.append((code, name))
    return languages
