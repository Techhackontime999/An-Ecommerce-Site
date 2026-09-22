from django.urls import path
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    path('shop/', views.product_list, name='product_list'),
    path('shop/search/', views.product_search, name='product_search'),
    path('shop/suggest/', views.search_suggestions, name='search_suggestions'),
    path('api/search/suggest/', views.search_suggest, name='search_suggest'),
    path('shop/<slug:category_slug>/', views.product_list, name='product_list_by_category'),
    path('shop/<int:id>/<slug:slug>/', views.product_detail, name='product_detail'),
]
