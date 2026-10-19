from django.urls import path

from customers import views as customer_views
from dashboard import views as dashboard_views
from orders import views as order_views

app_name = 'Customer'

urlpatterns = [
    path('', dashboard_views.customer_dashboard, name='dashboard'),
    path('cart/', customer_views.cart_view, name='cart'),
    path(
        'cart/add/<int:product_id>/',
        customer_views.add_to_cart,
        name='cart_add',
    ),
    path(
        'cart/update/<int:product_id>/',
        customer_views.update_cart_item,
        name='cart_update',
    ),
    path(
        'cart/remove/<int:product_id>/',
        customer_views.remove_from_cart,
        name='cart_remove',
    ),
    path('checkout/', order_views.checkout_view, name='checkout'),
    path('orders/', order_views.order_history, name='orders'),
    path(
        'orders/<str:order_number>/',
        order_views.order_detail,
        name='order_detail',
    ),
    path(
        'orders/<str:order_number>/cancel/',
        order_views.cancel_order,
        name='order_cancel',
    ),
]
