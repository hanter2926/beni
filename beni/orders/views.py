import uuid
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    role_group_required,
    user_has_role_group,
)
from customers.views import cart_for_customer

from .forms import CheckoutForm, OrderStatusForm
from .models import CheckoutAttempt, Order
from .services import (
    CART_SESSION_KEY,
    CHECKOUT_RECEIPTS_SESSION_KEY,
    CHECKOUT_STATE_SESSION_KEY,
    CheckoutError,
    OrderTransitionError,
    cart_digest,
    create_orders,
    get_checkout_replay,
    preview_cart,
    transition_order,
    valid_status_targets,
)

logger = logging.getLogger(__name__)


def _customer_only(request):
    user = request.user
    if (
        not user.is_authenticated
        or user.is_staff
        or user.is_superuser
        or user_has_role_group(user, SHOPKEEPER_GROUP)
        or user_has_role_group(user, REPAIR_WORKER_GROUP)
    ):
        raise PermissionDenied


def _render_checkout(request, form, items, total, token, errors=()):
    return render(
        request,
        'customer/checkout.html',
        {
            'form': form,
            'items': items,
            'subtotal': total,
            'delivery_fee': total * 0,
            'total': total,
            'checkout_token': token,
            'errors': errors,
            'role_label': 'Customer',
        },
    )


@login_required(login_url='accounts:login')
def checkout_view(request):
    _customer_only(request)
    cart = cart_for_customer(request)
    digest = cart_digest(cart)
    state = request.session.get(CHECKOUT_STATE_SESSION_KEY)
    if not isinstance(state, dict) or state.get('cart_digest') != digest:
        state = {'token': str(uuid.uuid4()), 'cart_digest': digest}
        request.session[CHECKOUT_STATE_SESSION_KEY] = state

    form = CheckoutForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        payment_method = form.cleaned_data['payment_method']
        if payment_method == 'razorpay':
            from django.core.exceptions import ImproperlyConfigured
            from payments.gateway import (
                PaymentProviderError,
                assert_configured,
            )
            from payments.services import PaymentWorkflowError

            try:
                assert_configured()
            except ImproperlyConfigured as exc:
                form.add_error(None, str(exc))

        try:
            token = uuid.UUID(request.POST.get('checkout_token', ''))
        except (TypeError, ValueError, AttributeError):
            token = None

        if form.errors:
            pass
        elif token is None:
            form.add_error(None, 'This checkout form is invalid. Please review it and try again.')
        else:
            receipts = request.session.get(CHECKOUT_RECEIPTS_SESSION_KEY, {})
            if isinstance(receipts, dict) and str(token) in receipts:
                replay = get_checkout_replay(token, request.user, receipts[str(token)])
                if replay is None:
                    form.add_error(None, 'This checkout could not be found. Please start a new checkout.')
                else:
                    attempt, orders = replay
                    if digest == attempt.cart_digest:
                        request.session[CART_SESSION_KEY] = {}
                    if state.get('token') == str(token):
                        request.session.pop(CHECKOUT_STATE_SESSION_KEY, None)
                    if attempt.payment_method == 'razorpay':
                        from payments.models import PaymentAttempt

                        payment_attempt = (
                            PaymentAttempt.objects.filter(
                                checkout_attempt=attempt,
                            )
                            .order_by('-created_at', '-id')
                            .first()
                        )
                        if payment_attempt is not None:
                            return redirect(
                                'payments:attempt',
                                payment_attempt_id=payment_attempt.pk,
                            )
                        return redirect(
                            reverse(
                                'customers:order_detail',
                                args=[orders[0].order_number],
                            )
                        )
                    return redirect(
                        reverse('customers:order_detail', args=[orders[0].order_number])
                    )
            elif state.get('token') != str(token) or state.get('cart_digest') != digest:
                form.add_error(None, 'Your cart changed after checkout opened. Please review it and try again.')
                state = {'token': str(uuid.uuid4()), 'cart_digest': digest}
                request.session[CHECKOUT_STATE_SESSION_KEY] = state
            else:
                try:
                    attempt, orders, _ = create_orders(
                        customer=request.user,
                        cart=cart,
                        token=token,
                        contact=form.cleaned_data,
                        payment_method=payment_method,
                    )
                except CheckoutError as exc:
                    form.add_error(None, str(exc))
                else:
                    receipts = request.session.get(CHECKOUT_RECEIPTS_SESSION_KEY, {})
                    if not isinstance(receipts, dict):
                        receipts = {}
                    receipts[str(token)] = attempt.cart_digest
                    request.session[CHECKOUT_RECEIPTS_SESSION_KEY] = dict(
                        list(receipts.items())[-10:]
                    )
                    if cart_digest(request.session.get(CART_SESSION_KEY, {})) == attempt.cart_digest:
                        request.session[CART_SESSION_KEY] = {}
                    request.session.pop(CHECKOUT_STATE_SESSION_KEY, None)
                    if payment_method == 'razorpay':
                        from payments.models import PaymentAttempt
                        from payments.services import (
                            PaymentWorkflowError,
                            create_payment_attempt,
                        )

                        try:
                            payment_attempt = create_payment_attempt(
                                checkout_attempt_id=attempt.pk,
                                customer=request.user,
                            )
                        except (
                            PaymentWorkflowError,
                            PaymentProviderError,
                        ) as exc:
                            logger.error(
                                'Unable to initialize online payment for checkout %s: %s',
                                attempt.pk,
                                exc,
                            )
                            messages.error(
                                request,
                                'Your orders were created but payment could not be '
                                f'initialized: {exc}',
                            )
                            payment_attempt = (
                                PaymentAttempt.objects.filter(
                                    checkout_attempt=attempt,
                                )
                                .order_by('-created_at', '-id')
                                .first()
                            )
                            if payment_attempt is not None:
                                return redirect(
                                    'payments:attempt',
                                    payment_attempt_id=payment_attempt.pk,
                                )
                            return redirect(
                                reverse(
                                    'customers:order_detail',
                                    args=[orders[0].order_number],
                                )
                            )
                        return redirect(
                            'payments:attempt',
                            payment_attempt_id=payment_attempt.pk,
                        )
                    messages.success(request, 'Your order was placed successfully.')
                    return redirect(
                        reverse('customers:order_detail', args=[orders[0].order_number])
                    )

    try:
        items, total = preview_cart(cart)
        errors = ()
    except CheckoutError as exc:
        items, total, errors = [], 0, (str(exc),)
        if request.method == 'GET':
            messages.error(request, str(exc))
            return redirect(reverse('customers:cart'))
        if not form.errors:
            form.add_error(None, str(exc))

    return _render_checkout(request, form, items, total, state['token'], errors)


@login_required(login_url='accounts:login')
def order_history(request):
    _customer_only(request)
    orders = (
        Order.objects.filter(customer=request.user)
        .select_related('shop')
        .prefetch_related('items')
    )
    return render(
        request,
        'customer/orders/list.html',
        {'orders': orders, 'role_label': 'Customer'},
    )


@login_required(login_url='accounts:login')
def order_detail(request, order_number):
    _customer_only(request)
    order = get_object_or_404(
        Order.objects.filter(customer=request.user)
        .select_related('shop')
        .prefetch_related('items'),
        order_number=order_number,
    )
    cancellation_request = None
    payment_attempt = None
    online_payment = (
        order.checkout_attempt.payment_method
        == CheckoutAttempt.PAYMENT_METHOD_RAZORPAY
    )
    if online_payment:
        from payments.models import OrderCancellationRequest, PaymentAttempt

        cancellation_request = OrderCancellationRequest.objects.filter(
            order=order,
        ).first()
        payment_attempt = (
            PaymentAttempt.objects.filter(
                checkout_attempt=order.checkout_attempt,
            )
            .order_by('-created_at', '-id')
            .first()
        )
    return render(
        request,
        'customer/orders/detail.html',
        {
            'order': order,
            'can_cancel': (
                order.status in (Order.STATUS_PENDING, Order.STATUS_CONFIRMED)
                and order.payment_status != Order.PAYMENT_PAID
                and (
                    not online_payment
                    or order.payment_status == Order.PAYMENT_FAILED
                )
            ),
            'can_request_cancel': (
                order.status in (Order.STATUS_PENDING, Order.STATUS_CONFIRMED)
                and order.payment_status == Order.PAYMENT_PAID
                and cancellation_request is None
            ),
            'cancellation_request': cancellation_request,
            'payment_attempt': payment_attempt,
            'can_start_payment': (
                online_payment
                and payment_attempt is None
                and order.payment_status != Order.PAYMENT_PAID
                and order.status not in (
                    Order.STATUS_CANCELLED,
                    Order.STATUS_REFUNDED,
                )
            ),
            'role_label': 'Customer',
        },
    )


@require_POST
@login_required(login_url='accounts:login')
def cancel_order(request, order_number):
    _customer_only(request)
    order = get_object_or_404(
        Order.objects.filter(customer=request.user),
        order_number=order_number,
    )
    if order.payment_status == Order.PAYMENT_PAID:
        from payments.forms import PaidOrderCancellationForm
        from payments.services import (
            PaymentWorkflowError,
            request_paid_order_cancellation,
        )

        form = PaidOrderCancellationForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Enter a reason for the cancellation request.')
            return redirect(reverse('customers:order_detail', args=[order_number]))
        try:
            request_paid_order_cancellation(
                order_number=order_number,
                customer=request.user,
                reason=form.cleaned_data['reason'],
            )
        except PaymentWorkflowError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                'Your cancellation request was submitted for staff review. '
                'A refund is not issued automatically.',
            )
        return redirect(reverse('customers:order_detail', args=[order_number]))
    try:
        order = transition_order(
            order_number=order_number,
            actor=request.user,
            new_status=Order.STATUS_CANCELLED,
        )
    except OrderTransitionError as exc:
        messages.error(request, str(exc))
    else:
        if order is None:
            messages.error(request, 'That order could not be found.')
        else:
            messages.success(request, 'The order was cancelled and its stock was restored.')
    return redirect(reverse('customers:orders'))


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_order_list(request):
    orders = list(
        Order.objects.filter(shop__owner=request.user)
        .select_related('shop', 'customer')
        .prefetch_related('items')
    )
    for order in orders:
        order.status_form = OrderStatusForm(
            allowed_statuses=valid_status_targets(
                order.status,
                payment_status=order.payment_status,
                payment_method=order.checkout_attempt.payment_method,
            ),
            current_status=order.status,
        )
    return render(
        request,
        'shopkeeper/orders/list.html',
        {
            'orders': orders,
            'role_label': 'Shopkeeper',
            'active_nav': 'orders',
        },
    )


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.filter(shop__owner=request.user)
        .select_related('shop', 'customer', 'checkout_attempt')
        .prefetch_related('items'),
        order_number=order_number,
    )
    return render(
        request,
        'shopkeeper/orders/detail.html',
        {
            'order': order,
            'status_form': OrderStatusForm(
                allowed_statuses=valid_status_targets(
                    order.status,
                    payment_status=order.payment_status,
                    payment_method=order.checkout_attempt.payment_method,
                ),
                current_status=order.status,
            ),
            'role_label': 'Shopkeeper',
            'active_nav': 'orders',
        },
    )


@require_POST
@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_order_update(request, order_number):
    order = get_object_or_404(
        Order.objects.filter(shop__owner=request.user),
        order_number=order_number,
    )
    form = OrderStatusForm(
        request.POST,
        allowed_statuses=valid_status_targets(
            order.status,
            payment_status=order.payment_status,
            payment_method=order.checkout_attempt.payment_method,
        ),
        current_status=order.status,
    )
    if not form.is_valid():
        messages.error(request, 'Choose a valid next status for this order.')
        return redirect(reverse('shopkeeper_orders'))
    try:
        changed = transition_order(
            order_number=order_number,
            actor=request.user,
            new_status=form.cleaned_data['status'],
            shopkeeper=True,
        )
    except OrderTransitionError as exc:
        messages.error(request, str(exc))
    else:
        if changed is None:
            messages.error(request, 'That order could not be found.')
        else:
            messages.success(request, 'Order status updated.')
    return redirect(reverse('shopkeeper_orders'))
