from django.urls import path
from . import views
from .views import signup
from .views import login_view
from .views import logout_view


app_name = 'auth'
urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
]
