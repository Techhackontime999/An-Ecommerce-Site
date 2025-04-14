from django.urls import path
from . import views

app_name = 'deals'

urlpatterns = [
    path('', views.todays_deals, name='todays_deals'),
]
