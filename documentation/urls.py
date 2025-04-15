from django.urls import path
from . import views
app_name='doc'
urlpatterns = [
    path('', views.documentation_view, name='documentation'),
    path('pdf/', views.download_pdf, name='download_pdf'),
    path('word/', views.download_word, name='download_word'),
]
