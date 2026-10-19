from django.urls import path

from dashboard import views as dashboard_views
from orders import views as order_views
from products import views as product_views
from shops import views as shop_views
from verification import views as verification_views
from wallets import views as wallet_views

app_name = 'Dukandaar'

urlpatterns = [
    path('', dashboard_views.shopkeeper_dashboard, name='dashboard'),
    path('shops/', shop_views.shop_list, name='shops'),
    path('shops/add/', shop_views.shop_create, name='shop_create'),
    path('shops/<int:shop_id>/edit/', shop_views.shop_update, name='shop_edit'),
    path('products/', product_views.product_list, name='products'),
    path('products/add/', product_views.product_create, name='product_create'),
    path(
        'products/<int:product_id>/edit/',
        product_views.product_update,
        name='product_edit',
    ),
    path('orders/', order_views.shopkeeper_order_list, name='orders'),
    path(
        'orders/<str:order_number>/',
        order_views.shopkeeper_order_detail,
        name='order_detail',
    ),
    path(
        'orders/<str:order_number>/status/',
        order_views.shopkeeper_order_update,
        name='order_update',
    ),
    path('wallet/', wallet_views.shopkeeper_wallet, name='wallet'),
    path(
        'verification/shops/<int:shop_id>/',
        verification_views.shopkeeper_application,
        name='shop_verification',
    ),
]
