from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .context_processors import DEFAULTS
from .currencies import CURRENCIES
from .forms import PreferenceForm
from .models import UserPreference

FIELDS = ('theme', 'language', 'currency', 'font_style', 'accent')

VALID = {
    'theme': set(dict(UserPreference.THEME_CHOICES)),
    'language': set(dict(UserPreference.LANG_CHOICES)),
    'font_style': set(dict(UserPreference.FONT_CHOICES)),
    'accent': set(dict(UserPreference.ACCENT_CHOICES)),
}


@require_POST
def toggle_theme(request):
    """Instant theme flip from the navbar button."""
    theme = request.POST.get('theme', '')
    if theme not in VALID['theme']:
        return JsonResponse({'error': 'invalid theme'}, status=400)

    if request.user.is_authenticated:
        obj, created = UserPreference.objects.get_or_create(user=request.user)
        obj.theme = theme
        obj.save(update_fields=['theme', 'updated_at'])
    else:
        prefs = dict(request.session.get('user_prefs', {}))
        prefs['theme'] = theme
        request.session['user_prefs'] = prefs

    return JsonResponse({'ok': True, 'theme': theme})


def settings_view(request):
    authenticated = request.user.is_authenticated
    obj = None
    if authenticated:
        obj, created = UserPreference.objects.get_or_create(user=request.user)
        prefs = {f: getattr(obj, f) for f in FIELDS}
    else:
        stored = dict(request.session.get('user_prefs', {}))
        prefs = {}
        for f in FIELDS:
            prefs[f] = stored.get(f, DEFAULTS.get(f, UserPreference._meta.get_field(f).default))

    if request.method == 'POST':
        if request.POST.get('reset') == '1':
            data = {
                'theme': 'light',
                'language': 'en',
                'currency': 'USD',
                'font_style': 'default',
                'accent': 'orange',
            }
            if authenticated:
                for f in FIELDS:
                    setattr(obj, f, data[f])
                obj.save()
            else:
                request.session['user_prefs'] = data
            translation.activate('en')
            request.session['django_language'] = 'en'
            messages.success(request, _("Your preferences have been reset to defaults."))
            response = redirect('preferences:settings')
            response.set_cookie(settings.LANGUAGE_COOKIE_NAME, 'en')
            return response

        form = PreferenceForm(request.POST)
        if form.is_valid():
            data = {f: form.cleaned_data[f] for f in FIELDS}
            if authenticated:
                for f in FIELDS:
                    setattr(obj, f, data[f])
                obj.save()
            else:
                request.session['user_prefs'] = data
            lang = data.get('language')
            if lang:
                translation.activate(lang)
                request.session['django_language'] = lang
            messages.success(request, _("Your preferences have been saved."))
            response = redirect('preferences:settings')
            if lang:
                response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
            return response
    else:
        form = PreferenceForm(initial=prefs)

    return render(request, 'preferences/settings.html', {
        'form': form,
        'currencies': CURRENCIES,
        'prefs': prefs,
    })
