from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('<int:product_id>/', views.create_review, name='create_review'),
    path('review/list/<int:product_id>/', views.product_review_list, name='product_review_list'),
    path('review/new/<int:product_id>/', views.create_product_review, name='create_product_review'),
    path('review/<int:review_id>/', views.product_review_detail, name='product_review_detail'),
    path('review/<int:review_id>/edit/', views.edit_product_review, name='edit_product_review'),
    path('review/<int:review_id>/helpful/', views.toggle_review_helpful, name='toggle_review_helpful'),
    path('review/<int:review_id>/report/', views.report_review, name='report_review'),
]
