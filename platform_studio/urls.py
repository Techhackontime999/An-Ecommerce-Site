from django.urls import path

from .views import platform_studio_view

app_name = 'platform_studio'

urlpatterns = [
    path('platform-studio/', platform_studio_view, name='platform_studio'),
]
