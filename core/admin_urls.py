from django.urls import path
from django.contrib import admin
from .admin_views import seed_data_view, clear_data_view

app_name = 'admin'

urlpatterns = [
    path('seed-data/', admin.site.admin_view(seed_data_view), name='seed_data'),
    path('clear-data/', admin.site.admin_view(clear_data_view), name='clear_data'),
]

urlpatterns += admin.site.urls[0]
