from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    user_has_role_group,
)
from orders.services import (
    CHECKOUT_RECEIPTS_SESSION_KEY,
    CHECKOUT_STATE_SESSION_KEY,
    invalidate_checkout_state,
)
from products.models import Product
from products.services import is_product_marketable, marketable_products

CART_SESSION_KEY = 'beni_cart'
CART_OWNER_SESSION_KEY = 'beni_cart_owner_id'


def is_customer_user(user):
    return (
        user.is_authenticated
        and not user.is_staff
        and not user.is_superuser
        and not user_has_role_group(user, SHOPKEEPER_GROUP)
        and not user_has_role_group(user, REPAIR_WORKER_GROUP)
    )


def cart_for_customer(request):
    customer_id = str(request.user.pk)
    if request.session.get(CART_OWNER_SESSION_KEY) != customer_id:
        request.session[CART_SESSION_KEY] = {}
        request.session[CART_OWNER_SESSION_KEY] = customer_id
        request.session.pop(CHECKOUT_STATE_SESSION_KEY, None)
        request.session.pop(CHECKOUT_RECEIPTS_SESSION_KEY, None)

    cart = request.session.get(CART_SESSION_KEY, {})
    if not isinstance(cart, dict):
        cart = {}
        request.session[CART_SESSION_KEY] = cart
    return cart


def _cart_from_session(request):
    return cart_for_customer(request)


def _save_cart(request, cart):
    request.session[CART_SESSION_KEY] = cart


def _customer_only(request):
    if not is_customer_user(request.user):
        raise PermissionDenied


def _line_total_for_item(item):
    price = Decimal(str(item.get('unit_price', '0.00')))
    quantity = int(item.get('quantity', 0))
    return price * quantity


def _resolve_cart_for_request(request):
    cart = _cart_from_session(request)
    items = []
    subtotal = Decimal('0.00')
    errors = []
    product_ids = set()
    for raw_key in cart:
        try:
            product_ids.add(int(raw_key))
        except (TypeError, ValueError):
            continue
    products_by_id = {
        product.pk: product
        for product in marketable_products(
            Product.objects.filter(pk__in=product_ids)
        ).select_related('shop')
    }
    removed_keys = []
    for raw_key, raw_item in cart.items():
        if not isinstance(raw_item, dict):
            errors.append('Your cart contains an invalid item. Please remove it and try again.')
            continue
        try:
            product_id = int(raw_key)
            if int(raw_item.get('product_id', product_id)) != product_id:
                raise ValueError
            quantity = int(raw_item.get('quantity', 1))
            unit_price = Decimal(str(raw_item.get('unit_price')))
        except (TypeError, ValueError, InvalidOperation):
            errors.append('Your cart contains invalid product information. Please remove it and try again.')
            continue
        product = products_by_id.get(product_id)
        if product is None:
            errors.append(
                'One or more products are no longer available and were removed from your cart.'
            )
            removed_keys.append(raw_key)
            continue
        if quantity <= 0:
            errors.append(f'{product.name} quantity must be greater than zero.')
            continue
        if quantity > product.stock_quantity:
            errors.append(f'Only {product.stock_quantity} {product.name} item(s) remain in stock.')
            continue
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

    if removed_keys:
        for raw_key in removed_keys:
            cart.pop(raw_key, None)
        _save_cart(request, cart)
        invalidate_checkout_state(request.session)

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

    product = get_object_or_404(
        Product.objects.select_related('shop'),
        pk=product_id,
    )
    if not is_product_marketable(product):
        messages.error(request, 'This product is no longer available.')
        return redirect(reverse('catalog:list'))
    if quantity > product.stock_quantity:
        messages.error(request, f'Only {product.stock_quantity} {product.name} item(s) remain in stock.')
        return redirect(reverse('catalog:detail', args=[product_id]))

    cart = _cart_from_session(request)
    cart_key = str(product_id)
    existing = cart.get(cart_key, {})
    try:
        existing_quantity = int(existing.get('quantity', 0)) if isinstance(existing, dict) else 0
    except (TypeError, ValueError):
        messages.error(request, 'Your cart contains invalid product information. Please review it first.')
        return redirect(reverse('customers:cart'))
    next_quantity = existing_quantity + quantity
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
    invalidate_checkout_state(request.session)
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
        messages.error(request, 'Please choose a quantity greater than zero.')
        return redirect(reverse('customers:cart'))

    cart = _cart_from_session(request)
    product = get_object_or_404(Product.objects.select_related('shop'), pk=product_id)
    if not is_product_marketable(product):
        messages.error(request, 'This product is no longer available.')
        return redirect(reverse('customers:cart'))
    if product.stock_quantity <= 0:
        messages.error(request, f'{product.name} is currently out of stock.')
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
    invalidate_checkout_state(request.session)
    messages.success(request, 'Your cart was updated.')
    return redirect(reverse('customers:cart'))


@require_POST
@login_required(login_url='accounts:login')
def remove_from_cart(request, product_id):
    _customer_only(request)
    cart = _cart_from_session(request)
    cart.pop(str(product_id), None)
    _save_cart(request, cart)
    invalidate_checkout_state(request.session)
    messages.success(request, 'Item removed from cart.')
    return redirect(reverse('customers:cart'))
