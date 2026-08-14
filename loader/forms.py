from django import forms

from .models import LoaderConfig


class LoaderConfigForm(forms.ModelForm):
    """Form for the Loader Studio page.

    ``version`` and ``updated_at`` are managed by the model itself, so they are
    excluded from the form.
    """

    class Meta:
        model = LoaderConfig
        exclude = ('version', 'updated_at', 'skeleton_pages')
        widgets = {
            'background_color': forms.TextInput(attrs={'type': 'color', 'class': 'ls-color'}),
            'accent_color': forms.TextInput(attrs={'type': 'color', 'class': 'ls-color'}),
            'duration_ms': forms.NumberInput(attrs={'min': 400, 'max': 6000, 'step': 100}),
            'logo_text': forms.TextInput(attrs={'placeholder': 'Shop-Seed'}),
        }
