from django.urls import path
from django.contrib.auth import views as auth_views
from django.utils.decorators import method_decorator

from core.throttle import throttle
from . import views
from .views import signup
from .views import login_view
from .views import logout_view


app_name = 'accounts'

_password_reset = method_decorator(
    throttle('password-reset', max_requests=5, window_seconds=3600),
    name='dispatch',
)(auth_views.PasswordResetView)
_password_reset_confirm = method_decorator(
    throttle('password-reset-confirm', max_requests=20, window_seconds=3600),
    name='dispatch',
)(auth_views.PasswordResetConfirmView)

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('seller_register/', views.seller_register, name='seller_register'),
    path('become-seller/', views.become_seller, name='become_seller'),

    path('profile/', views.profile_view, name='profile'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('verify/', views.verify_view, name='verify'),
    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),
    path('resend-verification-email/', views.resend_verification_email, name='resend_verification_email'),
    path('verify-phone/', views.verify_phone, name='verify_phone'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('sellers/documents/<int:doc_id>/', views.serve_seller_document, name='seller_document'),

    path('password-reset/', _password_reset.as_view(
        template_name='accounts/password_reset_form.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url='/accounts/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', _password_reset_confirm.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url='/accounts/reset/done/',
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html',
    ), name='password_reset_complete'),
]
