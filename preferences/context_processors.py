from .currencies import DEFAULT_CURRENCY
from .exchange import all_currencies, currency_info
from .models import UserPreference

DEFAULTS = {
    'theme': 'light',
    'language': 'en',
    'currency': DEFAULT_CURRENCY,
    'font_style': 'default',
    'accent': 'orange',
    'text_size': 'regular',
}


def site_defaults():
    """Site-wide appearance defaults configured in Platform Studio.

    When a superuser has customised the default theme / accent / font / size /
    currency these values are used for visitors without their own preference.
    Falls back to the built-in defaults if the table is unavailable.
    """
    prefs = dict(DEFAULTS)
    try:
        from platform_studio.utils import get_setting
    except Exception:
        return prefs
    try:
        prefs['theme'] = get_setting('default_theme') or prefs['theme']
        prefs['currency'] = get_setting('default_currency') or prefs['currency']
        prefs['font_style'] = get_setting('default_font') or prefs['font_style']
        prefs['accent'] = get_setting('default_accent') or prefs['accent']
        prefs['text_size'] = get_setting('default_text_size') or prefs['text_size']
    except Exception:
        pass
    return prefs


def user_preferences(request):
    prefs = site_defaults()
    if request.user.is_authenticated:
        try:
            obj = UserPreference.objects.get(user=request.user)
        except UserPreference.DoesNotExist:
            obj = None
        if obj is not None:
            for field in prefs:
                prefs[field] = getattr(obj, field)
    else:
        session_prefs = request.session.get('user_prefs')
        if session_prefs:
            for field in prefs:
                if field in session_prefs:
                    prefs[field] = session_prefs[field]

    return {
        'user_prefs': prefs,
        'CURRENCY_CODE': prefs['currency'],
        'CURRENCY': currency_info(prefs['currency']),
        'CURRENCIES': all_currencies(),
    }
