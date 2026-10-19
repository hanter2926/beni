from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path(
        'orders/<str:order_number>/',
        views.order_invoice,
        name='order_invoice',
    ),
]
