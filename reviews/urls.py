from django.urls import path
from .views import create_review
app_name='reviews'
urlpatterns = [
    path('<int:product_id>/', create_review, name='create_review'),
]
