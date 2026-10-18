import hashlib
import json
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone

from products.models import Product
from products.services import eligible_shop_verifications, is_product_marketable
from shops.models import Shop

from notifications.services import create_notification
from .models import CheckoutAttempt, Order, OrderItem

CART_SESSION_KEY = 'beni_cart'
CHECKOUT_STATE_SESSION_KEY = 'beni_checkout_state'
CHECKOUT_RECEIPTS_SESSION_KEY = 'beni_checkout_receipts'

CENT = Decimal('0.01')
ZERO = Decimal('0.00')


class CheckoutError(Exception):
    pass


class OrderTransitionError(Exception):
    pass


def cart_digest(cart):
    payload = json.dumps(cart, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def invalidate_checkout_state(session):
    session.pop(CHECKOUT_STATE_SESSION_KEY, None)


def _cart_lines(cart):
    if not isinstance(cart, dict) or not cart:
        raise CheckoutError('Your cart is empty.')

    lines = []
    for raw_product_id, item in cart.items():
        if not isinstance(item, dict):
            raise CheckoutError('Your cart contains an invalid item. Please update it and try again.')
        try:
            product_id = int(raw_product_id)
            item_product_id = int(item.get('product_id', product_id))
            quantity = int(item.get('quantity'))
            stored_price = Decimal(str(item.get('unit_price')))
        except (TypeError, ValueError, InvalidOperation):
            raise CheckoutError('Your cart contains invalid product information. Please update it and try again.')
        if product_id <= 0 or item_product_id != product_id or quantity <= 0:
            raise CheckoutError('Your cart contains an invalid item. Please update it and try again.')
        if not stored_price.is_finite() or stored_price < ZERO:
            raise CheckoutError('Your cart contains an invalid price. Please update it and try again.')
        lines.append((product_id, quantity, stored_price))
    return sorted(lines)


def _load_products(lines, lock=False):
    product_ids = [product_id for product_id, _, _ in lines]
    queryset = Product.objects.filter(pk__in=product_ids).order_by('pk')
    if lock:
        queryset = queryset.select_for_update()
    products = {product.pk: product for product in queryset}
    missing = set(product_ids) - products.keys()
    if missing:
        raise CheckoutError('One or more products are no longer available.')

    shop_ids = sorted({product.shop_id for product in products.values()})
    shops = Shop.objects.filter(pk__in=shop_ids).select_related('owner').order_by('pk')
    if lock:
        shops = shops.select_for_update()
    shop_by_id = {shop.pk: shop for shop in shops}
    eligible_shop_ids = set(
        eligible_shop_verifications(
            shop_ids=shop_ids,
            lock=lock,
        ).values_list('shop_id', flat=True)
    )

    resolved = []
    for product_id, quantity, stored_price in lines:
        product = products[product_id]
        shop = shop_by_id.get(product.shop_id)
        if shop is None or not is_product_marketable(
            product,
            shop=shop,
            eligible_shop_ids=eligible_shop_ids,
        ):
            raise CheckoutError(
                f'{product.name} is no longer available from its shop.'
            )
        if product.price != stored_price:
            raise CheckoutError(f'{product.name} price changed. Review your cart before ordering.')
        if quantity > product.stock_quantity:
            raise CheckoutError(f'Only {product.stock_quantity} {product.name} item(s) remain in stock.')
        resolved.append((product, shop, quantity))
    return resolved


def preview_cart(cart):
    lines = _cart_lines(cart)
    resolved = _load_products(lines)
    items = []
    total = ZERO
    for product, shop, quantity in resolved:
        line_total = (product.price * quantity).quantize(CENT)
        items.append({
            'product_id': product.pk,
            'shop_id': shop.pk,
            'shop_name': shop.name,
            'name': product.name,
            'category': product.category,
            'quantity': quantity,
            'unit_price': product.price,
            'line_total': line_total,
            'image': product.image.url if product.image else '',
        })
        total += line_total
    return items, total


def _attempt_result(attempt):
    return list(attempt.orders.select_related('shop').prefetch_related('items').order_by('id'))


def get_checkout_replay(token, customer, expected_digest):
    try:
        attempt = CheckoutAttempt.objects.get(token=token, customer=customer)
    except CheckoutAttempt.DoesNotExist:
        return None
    if attempt.cart_digest != expected_digest:
        raise CheckoutError('This checkout has expired. Please start a new checkout.')
    return attempt, _attempt_result(attempt)


def create_orders(*, customer, cart, token, contact):
    digest = cart_digest(cart)
    try:
        return _create_orders_transaction(
            customer=customer,
            cart=cart,
            token=token,
            digest=digest,
            contact=contact,
        )
    except IntegrityError:
        # A concurrent request may have committed this token between the initial
        # lookup and the unique insert. Treat only that exact replay as success.
        existing = get_checkout_replay(token, customer, digest)
        if existing is None:
            raise
        return existing[0], existing[1], True


@transaction.atomic
def _create_orders_transaction(*, customer, cart, token, digest, contact):
    attempt = (
        CheckoutAttempt.objects.select_for_update()
        .filter(token=token)
        .first()
    )
    if attempt is not None:
        if attempt.customer_id != customer.pk or attempt.cart_digest != digest:
            raise CheckoutError('This checkout token is no longer valid. Please start a new checkout.')
        return attempt, _attempt_result(attempt), True

    lines = _cart_lines(cart)
    attempt = CheckoutAttempt.objects.create(
        customer=customer,
        token=token,
        cart_digest=digest,
    )
    resolved = _load_products(lines, lock=True)
    groups = defaultdict(list)
    for product, shop, quantity in resolved:
        groups[shop.pk].append((product, shop, quantity))

    orders = []
    for shop_id in sorted(groups):
        shop_lines = groups[shop_id]
        shop = shop_lines[0][1]
        subtotal = sum(
            (product.price * quantity for product, _, quantity in shop_lines),
            start=ZERO,
        ).quantize(CENT)
        delivery_fee = ZERO
        service_fee = ZERO
        order = Order.objects.create(
            customer=customer,
            shop=shop,
            checkout_attempt=attempt,
            order_number=f'BENI-{timezone.now():%Y%m%d}-{uuid.uuid4().hex[:24].upper()}',
            contact_name=contact['full_name'],
            contact_phone=contact['phone'],
            address_line1=contact['address_line1'],
            city=contact['city'],
            state=contact['state'],
            postal_code=contact['postal_code'],
            delivery_notes=contact.get('delivery_notes', ''),
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            service_fee=service_fee,
            total=subtotal + delivery_fee + service_fee,
        )
        order_items = []
        for product, _, quantity in shop_lines:
            unit_price = product.price.quantize(CENT)
            order_items.append(OrderItem(
                order=order,
                product=product,
                product_name=product.name,
                product_category=product.category,
                product_sku=product.sku,
                unit_price=unit_price,
                quantity=quantity,
                line_total=(unit_price * quantity).quantize(CENT),
            ))
            product.stock_quantity -= quantity
            product.save(update_fields=('stock_quantity', 'updated_at'))
        OrderItem.objects.bulk_create(order_items)
        orders.append(order)
        create_notification(
            recipient=customer,
            event_key=f'order:{order.pk}:placed:customer',
            title='Order placed',
            message=f'Your order {order.order_number} was placed.',
            destination_name='customers:order_detail',
            destination_args=(order.order_number,),
        )
        create_notification(
            recipient=shop.owner,
            event_key=f'order:{order.pk}:placed:shopkeeper',
            title='New shop order',
            message=f'Order {order.order_number} is ready for review.',
            destination_name='shopkeeper_order_detail',
            destination_args=(order.order_number,),
        )
    return attempt, orders, False


ORDER_TRANSITIONS = {
    Order.STATUS_PENDING: {
        Order.STATUS_CONFIRMED,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_CONFIRMED: {
        Order.STATUS_PROCESSING,
        Order.STATUS_CANCELLED,
    },
    Order.STATUS_PROCESSING: {Order.STATUS_READY_FOR_PICKUP},
    Order.STATUS_READY_FOR_PICKUP: {Order.STATUS_OUT_FOR_DELIVERY},
    Order.STATUS_OUT_FOR_DELIVERY: {Order.STATUS_DELIVERED},
    Order.STATUS_DELIVERED: set(),
    Order.STATUS_CANCELLED: set(),
    Order.STATUS_REFUNDED: set(),
}


@transaction.atomic
def transition_order(*, order_number, actor, new_status, shopkeeper=False):
    order = (
        Order.objects.select_for_update()
        .select_related('shop')
        .filter(order_number=order_number)
        .first()
    )
    if order is None:
        return None

    if shopkeeper:
        if order.shop.owner_id != actor.pk:
            return None
    elif order.customer_id != actor.pk:
        return None

    if new_status not in ORDER_TRANSITIONS.get(order.status, set()):
        raise OrderTransitionError('That order status change is not allowed.')

    if new_status == Order.STATUS_CANCELLED:
        items = list(order.items.select_related('product').order_by('product_id'))
        products = Product.objects.filter(
            pk__in=[item.product_id for item in items]
        ).order_by('pk').select_for_update()
        products_by_id = {product.pk: product for product in products}
        if len(products_by_id) != len({item.product_id for item in items}):
            raise OrderTransitionError('Inventory could not be restored for this order.')
        if any(product.shop_id != order.shop_id for product in products_by_id.values()):
            raise OrderTransitionError(
                'Inventory cannot be restored because an ordered product changed shops.'
            )
        for item in items:
            product = products_by_id[item.product_id]
            product.stock_quantity += item.quantity
            product.save(update_fields=('stock_quantity', 'updated_at'))

    old_status = order.status
    order.status = new_status
    order.save(update_fields=('status', 'updated_at'))

    if shopkeeper:
        recipient = order.customer
        destination_name = 'customers:order_detail'
        destination_args = (order.order_number,)
        recipient_role = 'customer'
    else:
        recipient = order.shop.owner
        destination_name = 'shopkeeper_order_detail'
        destination_args = (order.order_number,)
        recipient_role = 'shopkeeper'
    create_notification(
        recipient=recipient,
        event_key=f'order:{order.pk}:status:{old_status}:{new_status}:{recipient_role}',
        title='Order status updated',
        message=(
            f'Order {order.order_number} is now '
            f'{order.get_status_display().lower()}.'
        ),
        destination_name=destination_name,
        destination_args=destination_args,
    )
    return order


def valid_status_targets(status):
    return sorted(ORDER_TRANSITIONS.get(status, set()))
