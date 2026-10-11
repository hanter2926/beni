from django.urls import path

from . import views

app_name = 'shops'

urlpatterns = [
    path('', views.shop_list, name='list'),
    path('add/', views.shop_create, name='create'),
    path('<int:shop_id>/edit/', views.shop_update, name='edit'),
]