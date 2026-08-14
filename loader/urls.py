from django.urls import path

from .views import loader_config_json

app_name = 'loader'

urlpatterns = [
    path('api/loader/config.json', loader_config_json, name='loader_config_json'),
]
