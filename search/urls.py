# shop/urls.py
from django.urls import path
from . import views

app_name='search'
urlpatterns = [
    # your existing urls...
    path("search/", views.product_search, name="product_search"),
]
