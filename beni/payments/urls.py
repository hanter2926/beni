from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path(
        'attempt/<int:payment_attempt_id>/',
        views.payment_attempt_view,
        name='attempt',
    ),
    path(
        'attempt/<int:payment_attempt_id>/verify/',
        views.verify_payment_view,
        name='verify',
    ),
    path(
        'checkout/<int:checkout_attempt_id>/start/',
        views.start_payment_view,
        name='start',
    ),
    path('webhook/razorpay/', views.razorpay_webhook, name='razorpay_webhook'),
    path('cancellations/', views.cancellation_queue, name='cancellation_queue'),
    path(
        'cancellations/<int:request_id>/review/',
        views.review_cancellation,
        name='review_cancellation',
    ),
]
