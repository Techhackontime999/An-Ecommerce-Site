from django.urls import path
from . import views
from .views import signup
from .views import login_view
from .views import logout_view


app_name = 'auth'
urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('seller_register/', views.seller_register, name='seller_register'),

    path('profile/', views.profile_view, name='profile'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
