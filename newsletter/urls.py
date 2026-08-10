from django.urls import path

from . import views

app_name = 'newsletter'

urlpatterns = [
    path('subscribe/', views.subscribe, name='subscribe'),
    path('confirm/<str:token>/', views.confirm, name='confirm'),
    path('unsubscribe/<str:token>/', views.unsubscribe, name='unsubscribe'),
]
