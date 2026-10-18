from django.urls import path

from . import views

urlpatterns = [
    path('', views.shopkeeper_order_list, name='shopkeeper_orders'),
]
