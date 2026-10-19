import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseServerError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    user_has_role_group,
)
from orders.models import CheckoutAttempt, Order

from . import gateway
from .forms import CancellationReviewForm
from .models import OrderCancellationRequest, PaymentAttempt
from .services import (
    PaymentValidationError,
    PaymentWorkflowError,
    create_payment_attempt,
    process_webhook,
    review_cancellation_request,
    verify_checkout_payment,
)
from .services import amount_in_subunits


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


def _customer_order_detail(payment_attempt):
    order = (
        Order.objects.filter(
            checkout_attempt=payment_attempt.checkout_attempt,
        )
        .order_by('id')
        .first()
    )
    if order is None:
        raise PaymentWorkflowError('No order exists for this payment attempt.')
    return reverse('customers:order_detail', args=[order.order_number])


@login_required(login_url='accounts:login')
def payment_attempt_view(request, payment_attempt_id):
    _customer_only(request)
    payment_attempt = get_object_or_404(
        PaymentAttempt.objects.select_related('checkout_attempt'),
        pk=payment_attempt_id,
        checkout_attempt__customer=request.user,
    )
    orders = Order.objects.filter(
        checkout_attempt=payment_attempt.checkout_attempt,
    ).select_related('shop')
    checkout_paid = orders.filter(payment_status=Order.PAYMENT_PAID).exists()
    try:
        key_id = gateway.get_public_key_id()
    except ImproperlyConfigured:
        key_id = ''
    return render(
        request,
        'payments/attempt.html',
        {
            'payment_attempt': payment_attempt,
            'orders': orders,
            'checkout_paid': checkout_paid,
            'key_id': key_id,
            'amount_subunits': amount_in_subunits(payment_attempt.amount),
            'order_detail_url': _customer_order_detail(payment_attempt),
            'role_label': 'Customer',
        },
    )


@require_POST
@login_required(login_url='accounts:login')
def start_payment_view(request, checkout_attempt_id):
    _customer_only(request)
    checkout_attempt = get_object_or_404(
        CheckoutAttempt,
        pk=checkout_attempt_id,
        customer=request.user,
        payment_method=CheckoutAttempt.PAYMENT_METHOD_RAZORPAY,
    )
    try:
        payment_attempt = create_payment_attempt(
            checkout_attempt_id=checkout_attempt.pk,
            customer=request.user,
        )
    except (ImproperlyConfigured, PaymentWorkflowError, gateway.PaymentProviderError) as exc:
        logger.warning(
            'Unable to start payment for checkout %s: %s',
            checkout_attempt.pk,
            exc,
        )
        messages.error(request, str(exc))
        payment_attempt = (
            PaymentAttempt.objects.filter(checkout_attempt=checkout_attempt)
            .order_by('-created_at', '-id')
            .first()
        )
        if payment_attempt is not None:
            return redirect(
                'payments:attempt',
                payment_attempt_id=payment_attempt.pk,
            )
        order = Order.objects.filter(checkout_attempt=checkout_attempt).order_by('id').first()
        if order is not None:
            return redirect('customers:order_detail', order_number=order.order_number)
        return redirect('customers:orders')
    return redirect('payments:attempt', payment_attempt_id=payment_attempt.pk)


@require_POST
@login_required(login_url='accounts:login')
def verify_payment_view(request, payment_attempt_id):
    _customer_only(request)
    payment_attempt = get_object_or_404(
        PaymentAttempt.objects.select_related('checkout_attempt'),
        pk=payment_attempt_id,
        checkout_attempt__customer=request.user,
    )
    try:
        verified_attempt = verify_checkout_payment(
            payment_attempt_id=payment_attempt.pk,
            customer=request.user,
            order_id=request.POST.get('razorpay_order_id', ''),
            payment_id=request.POST.get('razorpay_payment_id', ''),
            signature=request.POST.get('razorpay_signature', ''),
        )
    except (
        ImproperlyConfigured,
        PaymentValidationError,
        PaymentWorkflowError,
        gateway.PaymentProviderError,
    ) as exc:
        logger.warning(
            'Payment verification failed for attempt %s: %s',
            payment_attempt.pk,
            exc,
        )
        messages.error(request, str(exc))
    else:
        if verified_attempt.status == PaymentAttempt.STATUS_CAPTURED:
            messages.success(request, 'Payment captured and orders updated.')
        else:
            messages.info(
                request,
                'Payment is authorized; the order will update when capture is confirmed.',
            )
    return redirect(
        'payments:attempt',
        payment_attempt_id=payment_attempt.pk,
    )


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    try:
        processed = process_webhook(
            body=request.body,
            signature=request.META.get('HTTP_X_RAZORPAY_SIGNATURE', ''),
            event_id=request.META.get('HTTP_X_RAZORPAY_EVENT_ID', ''),
        )
    except ImproperlyConfigured as exc:
        logger.error('Razorpay webhook configuration error: %s', exc)
        return HttpResponseServerError('Webhook configuration is incomplete.')
    except PaymentValidationError as exc:
        logger.warning('Rejected Razorpay webhook: %s', exc)
        return HttpResponseBadRequest('Invalid webhook.')
    except PaymentWorkflowError as exc:
        logger.error('Unable to process Razorpay webhook: %s', exc)
        return HttpResponseServerError('Webhook could not be processed.')
    return HttpResponse('duplicate' if not processed else 'ok')


@login_required(login_url='accounts:login')
@user_passes_test(lambda user: user.is_active and user.is_staff)
def cancellation_queue(request):
    cancellations = (
        OrderCancellationRequest.objects.filter(
            status=OrderCancellationRequest.STATUS_PENDING,
        )
        .select_related('order', 'order__customer', 'order__shop')
    )
    return render(
        request,
        'payments/cancellation_queue.html',
        {
            'cancellations': cancellations,
            'review_form': CancellationReviewForm(),
            'role_label': 'Administrator',
        },
    )


@require_POST
@login_required(login_url='accounts:login')
@user_passes_test(lambda user: user.is_active and user.is_staff)
def review_cancellation(request, request_id):
    form = CancellationReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Review notes must be 1,000 characters or fewer.')
        return redirect('payments:cancellation_queue')
    action = request.POST.get('action')
    if action not in ('approve', 'reject'):
        return HttpResponseBadRequest('Invalid review action.')
    try:
        review_cancellation_request(
            request_id=request_id,
            reviewer=request.user,
            approve=action == 'approve',
            notes=form.cleaned_data['notes'],
        )
    except PaymentWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Cancellation request reviewed.')
    return redirect('payments:cancellation_queue')
