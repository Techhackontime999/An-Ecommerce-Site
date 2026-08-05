from django import forms

from .settings_definitions import settings_in_group


def build_group_form(group_key, initial=None):
    """Build a Django form with one field per setting in ``group_key``."""
    fields = {}
    for s in settings_in_group(group_key):
        field_type = s['field_type']
        label = s['label']
        help_text = s['help_text']
        default = s['default']

        if field_type == 'boolean':
            field = forms.BooleanField(required=False, label=label, help_text=help_text)
        elif field_type == 'textarea':
            field = forms.CharField(
                required=False, label=label, help_text=help_text,
                widget=forms.Textarea(attrs={'rows': 4}),
            )
        elif field_type == 'select':
            field = forms.ChoiceField(
                required=False, label=label, help_text=help_text,
                choices=s['choices'],
            )
        elif field_type == 'color':
            field = forms.CharField(
                required=False, label=label, help_text=help_text,
                widget=forms.TextInput(attrs={'type': 'color'}),
            )
        elif field_type == 'number':
            field = forms.CharField(required=False, label=label, help_text=help_text)
        else:
            field = forms.CharField(required=False, label=label, help_text=help_text)

        value = (initial or {}).get(s['key'], default)

        if field_type == 'boolean':
            field.initial = str(value).strip().lower() in ('1', 'true', 'yes', 'on')
        else:
            field.initial = value if value != '' else default

        fields[s['key']] = field

    return type('PlatformStudioForm', (forms.Form,), fields)


def form_initial_values(group_key, site_settings):
    """Pull the current stored values for a group into a form-initial dict."""
    from .settings_definitions import settings_in_group

    values = {}
    for s in settings_in_group(group_key):
        values[s['key']] = site_settings.get(s['key'], s['default'])
    return values


def save_group_form(form, group_key):
    """Persist cleaned data for a group back into SiteSetting rows."""
    from .utils import store_setting

    if not form.is_valid():
        return False
    for key, value in form.cleaned_data.items():
        if value is True:
            value = '1'
        elif value is False:
            value = '0'
        store_setting(key, value)
    return True
