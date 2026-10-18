from decimal import Decimal
import hashlib
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    role_group_required,
    user_has_role_group,
)
from products.models import Product

from .forms import CheckoutForm

CART_SESSION_KEY = 'beni_cart'
ORDER_SESSION_KEY = 'beni_orders'
ORDER_SIGNATURE_KEY = 'beni_order_signatures'


def is_customer_user(user):
    return (
        user.is_authenticated
        and not user.is_staff
        and not user_has_role_group(user, SHOPKEEPER_GROUP)
        and not user_has_role_group(user, REPAIR_WORKER_GROUP)
    )


def _cart_from_session(request):
    cart = request.session.get(CART_SESSION_KEY, {})
    if not isinstance(cart, dict):
        return {}
    return cart


def _save_cart(request, cart):
    request.session[CART_SESSION_KEY] = cart


def _customer_only(request):
    if not is_customer_user(request.user):
        raise PermissionDenied


def _order_signatures(request):
    signatures = request.session.get(ORDER_SIGNATURE_KEY, [])
    if not isinstance(signatures, list):
        return []
    return signatures


def _cart_signature(cart):
    payload = json.dumps(cart, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _line_total_for_item(item):
    price = Decimal(str(item.get('unit_price', '0.00')))
    quantity = int(item.get('quantity', 0))
    return price * quantity


def _resolve_cart_for_request(request):
    cart = _cart_from_session(request)
    items = []
    subtotal = Decimal('0.00')
    errors = []
    for raw_key, raw_item in cart.items():
        if not isinstance(raw_item, dict):
            continue
        product_id = raw_item.get('product_id')
        if product_id is None:
            continue
        product = Product.objects.filter(pk=product_id).select_related('shop').first()
        if product is None:
            errors.append('One or more products are no longer available.')
            continue
        if not product.is_active or not product.shop.is_active:
            errors.append(f'{product.name} is no longer available from its shop.')
            continue
        quantity = int(raw_item.get('quantity', 1))
        if quantity <= 0:
            errors.append(f'{product.name} quantity must be greater than zero.')
            continue
        if quantity > product.stock_quantity:
            errors.append(f'Only {product.stock_quantity} {product.name} item(s) remain in stock.')
            continue
        unit_price = Decimal(str(raw_item.get('unit_price', product.price)))
        if unit_price != product.price:
            errors.append(f'{product.name} price changed and was not accepted.')
            continue
        item = {
            'product_id': product.pk,
            'shop_id': product.shop_id,
            'shop_name': product.shop.name,
            'name': product.name,
            'category': product.category,
            'quantity': quantity,
            'unit_price': str(product.price),
            'image': product.image.url if product.image else '',
        }
        item['line_total'] = str(_line_total_for_item(item))
        items.append(item)
        subtotal += Decimal(str(item['line_total']))

    return items, subtotal, errors


@login_required(login_url='accounts:login')
def cart_view(request):
    _customer_only(request)
    items, subtotal, errors = _resolve_cart_for_request(request)
    delivery_fee = Decimal('0.00')
    total = subtotal + delivery_fee
    return render(
        request,
        'customer/cart.html',
        {
            'items': items,
            'subtotal': subtotal,
            'delivery_fee': delivery_fee,
            'total': total,
            'errors': errors,
            'role_label': 'Customer',
        },
    )


@require_POST
@login_required(login_url='accounts:login')
def add_to_cart(request, product_id):
    _customer_only(request)
    try:
        quantity = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        messages.error(request, 'Please choose a valid quantity.')
        return redirect(reverse('catalog:detail', args=[product_id]))
    if quantity <= 0:
        messages.error(request, 'Please choose a valid quantity.')
        return redirect(reverse('catalog:detail', args=[product_id]))

    product = get_object_or_404(Product.objects.select_related('shop'), pk=product_id)
    if not product.is_active or not product.shop.is_active:
        messages.error(request, 'This product is no longer available.')
        return redirect(reverse('catalog:list'))
    if quantity > product.stock_quantity:
        messages.error(request, f'Only {product.stock_quantity} {product.name} item(s) remain in stock.')
        return redirect(reverse('catalog:detail', args=[product_id]))

    cart = _cart_from_session(request)
    cart_key = str(product_id)
    existing = cart.get(cart_key, {})
    next_quantity = int(existing.get('quantity', 0)) + quantity
    if next_quantity > product.stock_quantity:
        messages.error(request, f'You can only add {product.stock_quantity} {product.name} item(s) to your cart.')
        return redirect(reverse('catalog:detail', args=[product_id]))

    cart[cart_key] = {
        'product_id': product.pk,
        'shop_id': product.shop_id,
        'shop_name': product.shop.name,
        'name': product.name,
        'category': product.category,
        'quantity': next_quantity,
        'unit_price': str(product.price),
        'image': product.image.url if product.image else '',
    }
    _save_cart(request, cart)
    messages.success(request, f'{product.name} was added to your cart.')
    return redirect(reverse('customers:cart'))


@require_POST
@login_required(login_url='accounts:login')
def update_cart_item(request, product_id):
    _customer_only(request)
    try:
        quantity = int(request.POST.get('quantity', '1'))
    except (TypeError, ValueError):
        messages.error(request, 'Please choose a valid quantity.')
        return redirect(reverse('customers:cart'))
    if quantity <= 0:
        return redirect(reverse('customers:cart'))

    cart = _cart_from_session(request)
    product = get_object_or_404(Product.objects.select_related('shop'), pk=product_id)
    if not product.is_active or not product.shop.is_active:
        messages.error(request, 'This product is no longer available.')
        return redirect(reverse('customers:cart'))
    if quantity > product.stock_quantity:
        messages.error(request, f'Only {product.stock_quantity} {product.name} item(s) remain in stock.')
        quantity = product.stock_quantity

    cart[str(product_id)] = {
        'product_id': product.pk,
        'shop_id': product.shop_id,
        'shop_name': product.shop.name,
        'name': product.name,
        'category': product.category,
        'quantity': quantity,
        'unit_price': str(product.price),
        'image': product.image.url if product.image else '',
    }
    _save_cart(request, cart)
    messages.success(request, 'Your cart was updated.')
    return redirect(reverse('customers:cart'))


@require_POST
@login_required(login_url='accounts:login')
def remove_from_cart(request, product_id):
    _customer_only(request)
    cart = _cart_from_session(request)
    cart.pop(str(product_id), None)
    _save_cart(request, cart)
    messages.success(request, 'Item removed from cart.')
    return redirect(reverse('customers:cart'))


@login_required(login_url='accounts:login')
def checkout_view(request):
    _customer_only(request)
    current_cart = _cart_from_session(request)
    cart_signature = _cart_signature(current_cart)
    last_checkout_signature = request.session.get('beni_last_checkout_signature')
    if cart_signature in _order_signatures(request) or (
        request.method == 'POST' and last_checkout_signature and not current_cart
    ):
        messages.error(request, 'This order has already been submitted. Please start a new checkout.')
        return redirect(reverse('customers:orders'))

    items, subtotal, errors = _resolve_cart_for_request(request)
    if not items:
        messages.error(request, 'Your cart is empty.')
        return redirect(reverse('customers:cart'))
    if errors:
        messages.error(request, 'Some items in your cart can no longer be purchased.')
        return redirect(reverse('customers:cart'))

    form = CheckoutForm(request.POST or None)
    delivery_fee = Decimal('0.00')
    total = subtotal + delivery_fee

    if request.method == 'POST' and form.is_valid():
        if cart_signature in _order_signatures(request):
            messages.error(request, 'This order has already been submitted. Please start a new checkout.')
            return redirect(reverse('customers:orders'))

        order_number = f"BENI-{timezone.now().strftime('%Y%m%d')}-{len(_order_signatures(request)) + 1:04d}"
        order = {
            'order_number': order_number,
            'customer_id': request.user.pk,
            'customer_name': request.user.get_username(),
            'created_at': timezone.now().isoformat(),
            'status': 'pending',
            'payment_status': 'not_started',
            'contact': {
                'full_name': form.cleaned_data['full_name'],
                'phone': form.cleaned_data['phone'],
            },
            'delivery_address': {
                'address_line1': form.cleaned_data['address_line1'],
                'city': form.cleaned_data['city'],
                'state': form.cleaned_data['state'],
                'postal_code': form.cleaned_data['postal_code'],
                'delivery_notes': form.cleaned_data['delivery_notes'],
            },
            'items': items,
            'subtotal': str(subtotal),
            'delivery_fee': str(delivery_fee),
            'total': str(total),
            'cart_signature': cart_signature,
        }
        orders = request.session.get(ORDER_SESSION_KEY, [])
        orders.insert(0, order)
        request.session[ORDER_SESSION_KEY] = orders
        signatures = _order_signatures(request)
        signatures.insert(0, cart_signature)
        request.session[ORDER_SIGNATURE_KEY] = signatures[:10]
        request.session['beni_last_checkout_signature'] = cart_signature
        request.session[CART_SESSION_KEY] = {}
        messages.success(request, f'Order {order_number} was created successfully.')
        return redirect(reverse('customers:order_detail', args=[order_number]))

    return render(
        request,
        'customer/checkout.html',
        {
            'form': form,
            'items': items,
            'subtotal': subtotal,
            'delivery_fee': delivery_fee,
            'total': total,
            'role_label': 'Customer',
        },
    )


@login_required(login_url='accounts:login')
def order_history(request):
    _customer_only(request)
    orders = []
    for order in request.session.get(ORDER_SESSION_KEY, []):
        if order.get('customer_id') == request.user.pk:
            orders.append(order)
    return render(
        request,
        'customer/orders/list.html',
        {
            'orders': orders,
            'role_label': 'Customer',
        },
    )


@login_required(login_url='accounts:login')
def order_detail(request, order_number):
    _customer_only(request)
    order = None
    for candidate in request.session.get(ORDER_SESSION_KEY, []):
        if candidate.get('order_number') == order_number and candidate.get('customer_id') == request.user.pk:
            order = candidate
            break
    if order is None:
        raise HttpResponseBadRequest('Order was not found.')
    return render(
        request,
        'customer/orders/detail.html',
        {'order': order, 'role_label': 'Customer'},
    )


@role_group_required(SHOPKEEPER_GROUP)
@login_required(login_url='accounts:login')
def shopkeeper_order_list(request):
    shop_ids = set(request.user.shops.values_list('id', flat=True))
    visible_orders = []
    for order in request.session.get(ORDER_SESSION_KEY, []):
        shop_items = [
            item for item in order.get('items', []) if item.get('shop_id') in shop_ids
        ]
        if shop_items:
            visible_orders.append({
                'order_number': order.get('order_number'),
                'status': order.get('status'),
                'customer_name': order.get('customer_name'),
                'created_at': order.get('created_at'),
                'items': shop_items,
                'total': order.get('total'),
            })
    return render(
        request,
        'shopkeeper/orders/list.html',
        {
            'orders': visible_orders,
            'role_label': 'Shopkeeper',
            'active_nav': 'orders',
        },
    )
