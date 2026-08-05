from functools import wraps

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import build_group_form, form_initial_values, save_group_form
from .models import SiteSetting
from .settings_definitions import GROUPS, GROUP_ORDER, iter_groups
from .utils import get_site_settings, invalidate, seed_defaults


def superuser_required(view_func):
    """Platform Studio is reserved for superusers only."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied(
                'Platform Studio is available to superusers only.'
            )
        return view_func(request, *args, **kwargs)
    return _wrapped


def _valid_group(group_key):
    return group_key if group_key in GROUPS else GROUP_ORDER[0]


def platform_studio_view(request):
    group_key = _valid_group(request.GET.get('group'))
    group_def = GROUPS[group_key]
    settings = get_site_settings()

    if SiteSetting.objects.count() == 0:
        seed_defaults()
        settings = get_site_settings()

    form = build_group_form(group_key, initial=form_initial_values(group_key, settings))()

    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        if action == 'reset':
            SiteSetting.objects.filter(group=group_key).delete()
            invalidate()
            messages.success(request, f'"{group_def["label"]}" settings were reset to defaults.')
            return redirect(f'{reverse("admin:platform_studio")}?group={group_key}')

        form = build_group_form(group_key, initial=form_initial_values(group_key, settings))(request.POST)
        if save_group_form(form, group_key):
            messages.success(request, f'"{group_def["label"]}" settings saved. Changes are live now.')
            return redirect(f'{reverse("admin:platform_studio")}?group={group_key}')
        messages.error(request, 'Please correct the errors below and try again.')

    ctx = admin.site.each_context(request)
    ctx.update({
        'page': 'platform_studio',
        'studio_groups': iter_groups(),
        'current_group': group_key,
        'current_group_def': group_def,
        'form': form,
        'setting_count': len([s for s in get_site_settings() if s]),
        'last_updated': (
            SiteSetting.objects.filter(group=group_key)
            .order_by('-updated_at')
            .values_list('updated_at', flat=True)
            .first()
        ),
    })
    return render(request, 'admin/pages/platform_studio.html', ctx)
