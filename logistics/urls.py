from django.urls import path
from django.views.decorators.csrf import csrf_exempt

from . import views

app_name = 'logistics'

urlpatterns = [
    # Public tracking
    path('track/', views.tracking_lookup, name='tracking_lookup'),
    path('track/<path:tracking_number>/', views.tracking_detail, name='tracking_detail'),

    # Courier webhook (no CSRF — signature-verified instead)
    path('api/webhooks/<str:courier_code>/', csrf_exempt(views.webhook), name='webhook'),

    # Staff dashboards
    path('dashboards/', views.dashboard, name='dashboard'),
    path('dashboards/shipments/', views.shipments_list, name='shipments'),
    path('dashboards/ndr/', views.ndr_queue, name='ndr_queue'),
    path('dashboards/returns/', views.returns_queue, name='returns_queue'),
]
