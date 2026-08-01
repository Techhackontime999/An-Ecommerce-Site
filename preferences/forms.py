from django import forms

from .currencies import CURRENCIES
from .models import UserPreference


class PreferenceForm(forms.Form):
    theme = forms.ChoiceField(
        choices=UserPreference.THEME_CHOICES,
        widget=forms.RadioSelect,
        required=False,
    )
    language = forms.ChoiceField(
        choices=UserPreference.LANG_CHOICES,
        required=False,
    )
    currency = forms.ChoiceField(
        choices=[(code, f"{info['name']} ({code})") for code, info in CURRENCIES.items()],
        required=False,
    )
    font_style = forms.ChoiceField(
        choices=UserPreference.FONT_CHOICES,
        required=False,
    )
    accent = forms.ChoiceField(
        choices=UserPreference.ACCENT_CHOICES,
        required=False,
    )
    text_size = forms.ChoiceField(
        choices=UserPreference.TEXT_SIZE_CHOICES,
        required=False,
    )
