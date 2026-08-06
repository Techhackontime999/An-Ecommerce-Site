from django.contrib import admin


def logistics_admin_context(request):
    """Provide Django admin context so LMS dashboards render inside admin chrome."""
    if not request.path.startswith('/logistics/'):
        return {}
    site = admin.site
    return {
        'site_title': site.site_title,
        'site_header': site.site_header,
        'site_url': site.site_url,
        'has_permission': site.has_permission(request),
        'available_apps': site.get_app_list(request),
        'is_popup': False,
        'is_nav_sidebar_enabled': site.enable_nav_sidebar,
        'log_entries': site.get_log_entries(request),
    }
