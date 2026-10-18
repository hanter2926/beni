from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('customer/', views.customer_dashboard, name='customer'),
    path('shopkeeper/', views.shopkeeper_dashboard, name='shopkeeper'),
    path('repair-worker/', views.repair_worker_dashboard, name='repair_worker'),
    path('admin/', views.admin_dashboard, name='admin'),
    path('admin/users/', views.admin_user_list, name='admin_users'),
]