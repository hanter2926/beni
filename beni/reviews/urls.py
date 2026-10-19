from django.urls import path

from . import views

app_name = 'reviews'

urlpatterns = [
    path('customer/', views.customer_review_list, name='customer_list'),
    path(
        'orders/<str:order_number>/submit/',
        views.submit_order_review_view,
        name='submit_order',
    ),
    path(
        'repairs/<int:booking_id>/submit/',
        views.submit_repair_review_view,
        name='submit_repair',
    ),
    path('shopkeeper/', views.shopkeeper_review_list, name='shopkeeper_list'),
    path('repair-worker/', views.worker_review_list, name='worker_list'),
    path('moderation/', views.moderation_queue, name='moderation_queue'),
    path(
        'moderation/<int:review_id>/',
        views.moderate_review_view,
        name='moderate',
    ),
]
