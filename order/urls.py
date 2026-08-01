from django.urls import path
from . import views

app_name = 'order'

urlpatterns = [
    path('create/', views.order_create, name='order_create'),
    path('locate/', views.autofill_address, name='autofill_address'),
    path('my-orders/', views.my_orders, name='my_orders'),
]