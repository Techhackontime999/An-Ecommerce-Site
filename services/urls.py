from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('', views.services_list, name='services_list'),
    path('<int:pk>/', views.service_detail, name='service_detail'),
]
