from django.urls import path
from django.contrib import admin
from .admin_views import (
    seed_data_view,
    clear_data_view,
    research_insights_view,
    analytics_view,
    marketing_view,
)
from platform_studio.views import platform_studio_view, superuser_required
from loader.views import loader_studio_view

app_name = 'admin'

urlpatterns = [
    path('seed-data/', admin.site.admin_view(seed_data_view), name='seed_data'),
    path('clear-data/', admin.site.admin_view(clear_data_view), name='clear_data'),
    path('research-insights/', admin.site.admin_view(research_insights_view), name='research_insights'),
    path('analytics/', admin.site.admin_view(analytics_view), name='analytics'),
    path('marketing/', admin.site.admin_view(marketing_view), name='marketing'),
    path('platform-studio/', admin.site.admin_view(superuser_required(platform_studio_view)), name='platform_studio'),
    path('loader-studio/', admin.site.admin_view(superuser_required(loader_studio_view)), name='loader_studio'),
]

urlpatterns += admin.site.urls[0]
