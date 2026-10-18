from django.urls import path

from orders import views

urlpatterns = [
    path('', views.shopkeeper_order_list, name='shopkeeper_orders'),
    path('<str:order_number>/', views.shopkeeper_order_detail, name='shopkeeper_order_detail'),
    path('<str:order_number>/status/', views.shopkeeper_order_update, name='shopkeeper_order_update'),
]
