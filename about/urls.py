# about/urls.py
from django.urls import path
from . import views
from .views import about_view
app_name='about'

urlpatterns = [
    path('', views.about_view, name='about'),
]
