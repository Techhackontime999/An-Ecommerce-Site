from django.urls import path
from . import views

app_name = 'deals'

urlpatterns = [
    path('', views.todays_deals, name='todays_deals'),
        # URL for displaying today's deals with optional category filter
    path('<slug:category_slug>/', views.todays_deals, name='todays_deals_by_category'),
]
