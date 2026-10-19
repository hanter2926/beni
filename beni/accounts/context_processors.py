from django.urls import reverse

from accounts.roles import REPAIR_WORKER_GROUP, SHOPKEEPER_GROUP, user_has_role_group
from customers.cart_constants import CART_OWNER_SESSION_KEY, CART_SESSION_KEY

PAGE_LABELS = {
    ('dashboard', 'customer'): 'Overview',
    ('dashboard', 'shopkeeper'): 'Overview',
    ('dashboard', 'repair_worker'): 'Overview',
    ('dashboard', 'admin'): 'Overview',
    ('catalog', 'list'): 'Product catalog',
    ('catalog', 'detail'): 'Product details',
    ('customers', 'cart'): 'Cart',
    ('customers', 'checkout'): 'Checkout',
    ('customers', 'orders'): 'Orders',
    ('customers', 'order_detail'): 'Order details',
    ('customers', 'order_cancel'): 'Order cancellation',
    ('bookings', 'customer_list'): 'Repair services',
    ('bookings', 'customer_create'): 'New repair request',
    ('bookings', 'customer_detail'): 'Repair request details',
    ('bookings', 'worker_list'): 'Assigned jobs',
    ('bookings', 'worker_update'): 'Update job status',
    ('bookings', 'admin_list'): 'Repair bookings',
    ('bookings', 'admin_assign'): 'Assign repair worker',
    ('shops', 'list'): 'My shops',
    ('shops', 'create'): 'Add a shop',
    ('shops', 'edit'): 'Edit shop',
    ('products', 'list'): 'Products',
    ('products', 'create'): 'Add a product',
    ('products', 'edit'): 'Edit product',
    ('notifications', 'inbox'): 'Notifications',
    ('wallets', 'shopkeeper'): 'Wallet',
    ('wallets', 'repair_worker'): 'Wallet',
    ('verification', 'worker_application'): 'Verification',
    ('verification', 'admin_list'): 'Verification review',
    ('verification', 'admin_review'): 'Review verification',
    ('dashboard', 'admin_users'): 'Marketplace users',
    ('', 'shopkeeper_orders'): 'Shop orders',
    ('', 'shopkeeper_order_detail'): 'Order details',
    ('', 'shopkeeper_order_update'): 'Update order',
    ('billing', 'order_invoice'): 'Order receipt',
    ('reviews', 'customer_list'): 'My reviews',
    ('reviews', 'submit_order'): 'Write a review',
    ('reviews', 'submit_repair'): 'Write a repair review',
    ('reviews', 'shopkeeper_list'): 'Customer reviews',
    ('reviews', 'worker_list'): 'Customer reviews',
    ('reviews', 'moderation_queue'): 'Review moderation',
    ('reviews', 'moderate'): 'Moderate review',
}

WORKSPACE_URLS = {
    'Customer': 'dashboard:customer',
    'Shopkeeper': 'dashboard:shopkeeper',
    'Repair worker': 'dashboard:repair_worker',
    'Admin': 'dashboard:admin',
}


def navigation_context(request):
    user = request.user
    if not user.is_authenticated:
        return {}

    if user.is_staff:
        role_label = 'Admin'
    elif user_has_role_group(user, SHOPKEEPER_GROUP):
        role_label = 'Shopkeeper'
    elif user_has_role_group(user, REPAIR_WORKER_GROUP):
        role_label = 'Repair worker'
    else:
        role_label = 'Customer'

    context = {'role_label': role_label}
    workspace_route = WORKSPACE_URLS.get(role_label)
    if workspace_route:
        context['workspace_url'] = reverse(workspace_route)

    match = getattr(request, 'resolver_match', None)
    if match and match.url_name:
        context['current_page_label'] = PAGE_LABELS.get(
            (match.namespace or '', match.url_name),
            match.url_name.replace('_', ' ').capitalize(),
        )

    if (
        role_label == 'Customer'
        and request.session.get(CART_OWNER_SESSION_KEY) == str(user.pk)
    ):
        cart = request.session.get(CART_SESSION_KEY, {})
        if isinstance(cart, dict):
            context['cart_item_count'] = sum(
                quantity
                for item in cart.values()
                if isinstance(item, dict)
                and isinstance((quantity := item.get('quantity')), int)
                and not isinstance(quantity, bool)
                and quantity > 0
            )
        else:
            context['cart_item_count'] = 0
    else:
        context['cart_item_count'] = 0

    return context
