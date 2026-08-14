from functools import wraps

from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_control

from .forms import LoaderConfigForm
from .models import LoaderConfig
from .services import config_to_dict, get_config_dict


@cache_control(max_age=300, public=True)
def loader_config_json(request):
    """Public, cacheable JSON copy of the loader configuration.

    Served with ``Cache-Control: public, max-age=300`` so the versioned config
    can ride the HTTP cache. The engine treats the inline copy as the source of
    truth and only uses this endpoint to refresh its local cache.
    """
    return JsonResponse(get_config_dict())


def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Loader Studio is available to superusers only.')
        return view_func(request, *args, **kwargs)
    return _wrapped


def loader_studio_view(request):
    config = LoaderConfig.get_solo()

    if request.method == 'POST':
        form = LoaderConfigForm(request.POST, request.FILES, instance=config)
        if form.is_valid():
            form.save()
            LogEntry = _get_log_entry_model()
            LogEntry.objects.log_action(
                user_id=request.user.pk,
                content_type_id=ContentType.objects.get_for_model(LoaderConfig).pk,
                object_id=str(config.pk),
                object_repr='Loader Experience Configuration',
                action_flag=CHANGE,
                change_message='Updated Loader Studio settings. Changes are live.',
            )
            messages.success(request, 'Loader settings saved. Changes are live now.')
            return redirect(reverse('admin:loader_studio'))
        messages.error(request, 'Please correct the errors below and try again.')
    else:
        form = LoaderConfigForm(instance=config)

    ctx = admin.site.each_context(request)
    studio_config = config_to_dict(config)
    try:
        from platform_studio.utils import get_site_settings
        site_settings = get_site_settings()
        studio_config['site_name'] = site_settings.get('site_name', 'Shop-Seed')
        studio_config['logo_mark'] = site_settings.get('logo_mark', 'S')
    except Exception:
        studio_config['site_name'] = 'Shop-Seed'
        studio_config['logo_mark'] = 'S'
    ctx.update({
        'page': 'loader_studio',
        'form': form,
        'config': config,
        'config_dict': studio_config,
    })
    return render(request, 'admin/pages/loader_studio.html', ctx)


def _get_log_entry_model():
    from django.contrib.admin.models import LogEntry
    return LogEntry
