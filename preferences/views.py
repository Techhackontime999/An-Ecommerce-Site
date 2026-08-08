from datetime import timezone as dt_timezone

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from .context_processors import DEFAULTS
from .currencies import CURRENCIES
from .exchange import all_currencies, rates_updated_at
from .forms import PreferenceForm
from .models import UserPreference

FIELDS = ('theme', 'language', 'currency', 'font_style', 'accent', 'text_size')

VALID = {
    'theme': set(dict(UserPreference.THEME_CHOICES)),
    'language': set(dict(UserPreference.LANG_CHOICES)),
    'font_style': set(dict(UserPreference.FONT_CHOICES)),
    'accent': set(dict(UserPreference.ACCENT_CHOICES)),
    'text_size': set(dict(UserPreference.TEXT_SIZE_CHOICES)),
}

RESET_VALUES = {
    'theme': 'light',
    'language': 'en',
    'currency': 'USD',
    'font_style': 'default',
    'accent': 'orange',
    'text_size': 'regular',
}


def _store_prefs(obj, data, request):
    """Persist a full preference dict to the DB (authed) or session (guest)."""
    if obj is not None:
        for field in FIELDS:
            setattr(obj, field, data[field])
        obj.save()
    else:
        request.session['user_prefs'] = data


def _apply_language(data, request, response):
    """Activate the chosen language and persist it for the next request."""
    lang = data.get('language')
    if not lang:
        return response
    translation.activate(lang)
    request.session[settings.LANGUAGE_COOKIE_NAME] = lang
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)
    return response


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


@require_POST
def quick_prefs(request):
    """Lightweight preference update from the navbar dropdown.

    Guests get session-only prefs; signed-in users get DB-backed prefs.
    """
    updates = {}
    for field in FIELDS:
        value = request.POST.get(field)
        if value is None:
            continue
        if field == 'currency':
            if value in CURRENCIES:
                updates[field] = value
        elif field in VALID and value in VALID[field]:
            updates[field] = value
    if not updates:
        return JsonResponse({'error': 'no valid preferences supplied'}, status=400)

    obj = None
    if request.user.is_authenticated:
        obj, created = UserPreference.objects.get_or_create(user=request.user)

    if obj is not None:
        full = {f: getattr(obj, f) for f in FIELDS}
    else:
        full = dict(request.session.get('user_prefs', {}))
    for field, value in updates.items():
        full[field] = value
    _store_prefs(obj, full, request)

    response = JsonResponse({'ok': True, 'updated': sorted(updates)})
    return _apply_language(updates, request, response)


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
            _store_prefs(obj, dict(RESET_VALUES), request)
            messages.success(request, _("Your preferences have been reset to defaults."))
            response = redirect('preferences:settings')
            return _apply_language({'language': 'en'}, request, response)

        form = PreferenceForm(request.POST)
        if form.is_valid():
            data = {f: form.cleaned_data[f] for f in FIELDS}
            _store_prefs(obj, data, request)
            messages.success(request, _("Your preferences have been saved."))
            response = redirect('preferences:settings')
            return _apply_language(data, request, response)
    else:
        form = PreferenceForm(initial=prefs)

    updated_ts = rates_updated_at()
    rates_updated = (
        timezone.datetime.fromtimestamp(updated_ts, tz=dt_timezone.utc) if updated_ts else None
    )

    return render(request, 'preferences/settings.html', {
        'form': form,
        'currencies': all_currencies(),
        'rates_updated_at': rates_updated,
        'prefs': prefs,
    })
