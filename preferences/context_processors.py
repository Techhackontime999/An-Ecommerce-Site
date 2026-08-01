from .currencies import CURRENCIES, DEFAULT_CURRENCY
from .models import UserPreference

DEFAULTS = {
    'theme': 'light',
    'language': 'en',
    'currency': DEFAULT_CURRENCY,
    'font_style': 'default',
    'accent': 'orange',
}


def user_preferences(request):
    prefs = dict(DEFAULTS)
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

    currency_info = CURRENCIES.get(prefs['currency']) or CURRENCIES[DEFAULT_CURRENCY]
    return {
        'user_prefs': prefs,
        'CURRENCY_CODE': prefs['currency'],
        'CURRENCY': currency_info,
    }
