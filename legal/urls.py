from django.urls import path
from . import views

app_name = 'legal'

urlpatterns = [
    path('privacy/', views.PrivacyPolicyView.as_view(), name='privacy'),
    path('terms/', views.TermsOfServiceView.as_view(), name='terms'),
]
