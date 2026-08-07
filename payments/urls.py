from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('checkout/<int:order_id>/', views.checkout, name='checkout'),
    path('callback/', views.payment_callback, name='callback'),
    path('webhook/', views.payment_webhook, name='webhook'),
    path('verify/<int:order_id>/', views.payment_verify, name='verify'),
    path('success/<int:order_id>/', views.payment_success, name='success'),
    path('error/<int:order_id>/', views.payment_error, name='error'),
]
