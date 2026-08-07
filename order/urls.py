from django.urls import path
from . import views

app_name = 'order'

urlpatterns = [
    path('create/', views.order_create, name='order_create'),
    path('locate/', views.autofill_address, name='autofill_address'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/cancel/', views.order_cancel, name='order_cancel'),
    path('orders/<int:order_id>/return/', views.request_return, name='request_return'),
    path('orders/<int:order_id>/invoice/', views.order_invoice_pdf, name='order_invoice'),
]