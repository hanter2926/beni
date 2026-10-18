from django.urls import path

from . import views

app_name = 'verification'

urlpatterns = [
    path(
        'shopkeeper/shops/<int:shop_id>/',
        views.shopkeeper_application,
        name='shopkeeper_application',
    ),
    path(
        'repair-worker/',
        views.worker_application,
        name='worker_application',
    ),
    path('admin/', views.admin_application_list, name='admin_list'),
    path(
        'admin/<int:application_id>/review/',
        views.admin_application_review,
        name='admin_review',
    ),
]
