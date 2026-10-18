from django.urls import path

from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.customer_booking_list, name='customer_list'),
    path('new/', views.customer_booking_create, name='customer_create'),
    path('<int:booking_id>/', views.customer_booking_detail, name='customer_detail'),
    path('worker/', views.worker_booking_list, name='worker_list'),
    path(
        'worker/<int:booking_id>/status/',
        views.worker_booking_update,
        name='worker_update',
    ),
    path('admin/', views.admin_booking_list, name='admin_list'),
    path(
        'admin/<int:booking_id>/assign/',
        views.admin_booking_assign,
        name='admin_assign',
    ),
]
