from django.urls import path

from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='list'),
    path('add/', views.product_create, name='create'),
    path('<int:product_id>/edit/', views.product_update, name='edit'),
]