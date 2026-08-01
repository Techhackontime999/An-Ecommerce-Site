from django.urls import path

from . import views

app_name = 'preferences'

urlpatterns = [
    path('settings/', views.settings_view, name='settings'),
    path('toggle-theme/', views.toggle_theme, name='toggle_theme'),
]
