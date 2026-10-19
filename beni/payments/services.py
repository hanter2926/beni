import json
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from notifications.services import create_notification, notify_active_staff
from orders.models import CheckoutAttempt, Order
from orders.services import OrderTransitionError, transition_order

from . import gateway
from .models import OrderCancellationRequest, PaymentAttempt, WebhookEvent


ZERO = Decimal('0.00')


class PaymentWorkflowError(Exception):
    pass


class PaymentValidationError(Exception):
    pass


def amount_in_subunits(amount):
    normalized = Decimal(amount).quantize(Decimal('0.01'))
    return int(normalized * 100)


def _set_orders_payment_status(checkout_attempt_id, payment_status):
    Order.objects.filter(
        checkout_attempt_id=checkout_attempt_id,
    ).exclude(
        status__in=(Order.STATUS_CANCELLED, Order.STATUS_REFUNDED),
    ).update(
        payment_status=payment_status,
        updated_at=timezone.now(),
    )


def _sync_orders_payment_status(checkout_attempt_id):
    statuses = set(
        PaymentAttempt.objects.filter(
            checkout_attempt_id=checkout_attempt_id,
        ).values_list('status', flat=True)
    )
    if PaymentAttempt.STATUS_CAPTURED in statuses:
        payment_status = Order.PAYMENT_PAID
    elif statuses.intersection({
        PaymentAttempt.STATUS_PENDING,
        PaymentAttempt.STATUS_AUTHORIZED,
    }):
        payment_status = Order.PAYMENT_PENDING
    elif PaymentAttempt.STATUS_FAILED in statuses:
        payment_status = Order.PAYMENT_FAILED
    else:
        payment_status = Order.PAYMENT_NOT_STARTED
    _set_orders_payment_status(checkout_attempt_id, payment_status)


def _payment_attempt_total(checkout_attempt):
    totals = list(
        Order.objects.filter(checkout_attempt=checkout_attempt)
        .exclude(status__in=(Order.STATUS_CANCELLED, Order.STATUS_REFUNDED))
        .values_list('total', flat=True)
    )
    if not totals:
        raise PaymentWorkflowError('No orders exist for this checkout.')
    total = sum(totals, ZERO)
    if total <= ZERO:
        raise PaymentWorkflowError('The checkout total must be greater than zero.')
    return total.quantize(Decimal('0.01'))


def create_payment_attempt(*, checkout_attempt_id, customer):
    gateway.assert_configured()
    with transaction.atomic():
        checkout_attempt = (
            CheckoutAttempt.objects.select_for_update()
            .filter(pk=checkout_attempt_id, customer=customer)
            .first()
        )
        if checkout_attempt is None:
            raise PaymentWorkflowError('This checkout could not be found.')
        if checkout_attempt.payment_method != CheckoutAttempt.PAYMENT_METHOD_RAZORPAY:
            raise PaymentWorkflowError('This checkout is not an online payment.')
        if Order.objects.filter(
            checkout_attempt=checkout_attempt,
            payment_status=Order.PAYMENT_PAID,
        ).exists():
            raise PaymentWorkflowError('This checkout has already been paid.')

        previous = list(
            PaymentAttempt.objects.select_for_update()
            .filter(checkout_attempt=checkout_attempt)
            .order_by('-created_at', '-id')[:1]
        )
        if previous and previous[0].status in (
            PaymentAttempt.STATUS_PENDING,
            PaymentAttempt.STATUS_AUTHORIZED,
        ):
            if previous[0].provider_order_id:
                return previous[0]
            raise PaymentWorkflowError(
                'A payment attempt is already being created. Please refresh shortly.'
            )
        if previous and previous[0].status == PaymentAttempt.STATUS_CAPTURED:
            return previous[0]

        amount = _payment_attempt_total(checkout_attempt)
        payment_attempt = PaymentAttempt.objects.create(
            checkout_attempt=checkout_attempt,
            amount=amount,
        )
        _sync_orders_payment_status(checkout_attempt.pk)

    try:
        amount = amount_in_subunits(payment_attempt.amount)
        response = gateway.create_order(
            amount=amount,
            currency=payment_attempt.currency,
            receipt=f'beni-{payment_attempt.pk}',
            notes={'checkout_attempt': str(checkout_attempt.token)},
        )
        provider_order_id = response.get('id')
        if (
            not isinstance(provider_order_id, str)
            or not provider_order_id
            or response.get('amount') != amount
            or response.get('currency') != payment_attempt.currency
        ):
            raise gateway.PaymentProviderError(
                'Razorpay returned an invalid order reference or amount.'
            )
    except gateway.PaymentProviderError:
        with transaction.atomic():
            payment_attempt = PaymentAttempt.objects.select_for_update().get(
                pk=payment_attempt.pk
            )
            payment_attempt.status = PaymentAttempt.STATUS_FAILED
            payment_attempt.save(update_fields=('status', 'updated_at'))
            _sync_orders_payment_status(checkout_attempt.pk)
        raise

    payment_attempt.provider_order_id = provider_order_id
    payment_attempt.save(update_fields=('provider_order_id', 'updated_at'))
    return payment_attempt


def _apply_payment_status(attempt, status, payment_id):
    if attempt.status == PaymentAttempt.STATUS_CAPTURED:
        if payment_id != attempt.provider_payment_id:
            raise PaymentValidationError(
                'This checkout already has a different captured payment.'
            )
        return
    if status == PaymentAttempt.STATUS_AUTHORIZED:
        if attempt.status != PaymentAttempt.STATUS_PENDING:
            return
        if attempt.provider_payment_id and attempt.provider_payment_id != payment_id:
            raise PaymentValidationError(
                'This payment attempt already references a different payment.'
            )
        attempt.status = PaymentAttempt.STATUS_AUTHORIZED
        attempt.provider_payment_id = payment_id
        attempt.save(
            update_fields=(
                'status',
                'provider_payment_id',
                'updated_at',
            )
        )
        return
    if status == PaymentAttempt.STATUS_FAILED:
        if attempt.status in (
            PaymentAttempt.STATUS_AUTHORIZED,
            PaymentAttempt.STATUS_CAPTURED,
        ):
            return
        if attempt.provider_payment_id and attempt.provider_payment_id != payment_id:
            raise PaymentValidationError(
                'This payment attempt already references a different payment.'
            )
        attempt.status = PaymentAttempt.STATUS_FAILED
        attempt.provider_payment_id = payment_id
        attempt.save(
            update_fields=(
                'status',
                'provider_payment_id',
                'updated_at',
            )
        )
        _sync_orders_payment_status(
            attempt.checkout_attempt_id,
        )
        return
    if status == PaymentAttempt.STATUS_CAPTURED:
        if attempt.provider_payment_id and attempt.provider_payment_id != payment_id:
            raise PaymentValidationError(
                'This payment attempt already references a different payment.'
            )
        attempt.status = PaymentAttempt.STATUS_CAPTURED
        attempt.provider_payment_id = payment_id
        attempt.save(
            update_fields=(
                'status',
                'provider_payment_id',
                'updated_at',
            )
        )
        _sync_orders_payment_status(
            attempt.checkout_attempt_id,
        )


def _update_attempt_from_provider(*, payment_attempt_id, payment):
    if not isinstance(payment, dict):
        raise PaymentValidationError('Razorpay returned invalid payment details.')

    with transaction.atomic():
        initial_attempt = PaymentAttempt.objects.filter(
            pk=payment_attempt_id,
        ).only('checkout_attempt_id').first()
        if initial_attempt is None:
            raise PaymentWorkflowError('This payment attempt could not be found.')
        CheckoutAttempt.objects.select_for_update().get(
            pk=initial_attempt.checkout_attempt_id,
        )
        attempt = (
            PaymentAttempt.objects.select_for_update()
            .select_related('checkout_attempt')
            .filter(pk=payment_attempt_id)
            .first()
        )
        if attempt is None:
            raise PaymentWorkflowError('This payment attempt could not be found.')

        payment_id = payment.get('id')
        if (
            not isinstance(payment_id, str)
            or payment.get('order_id') != attempt.provider_order_id
            or payment.get('amount') != amount_in_subunits(attempt.amount)
            or payment.get('currency') != attempt.currency
        ):
            raise PaymentValidationError(
                'The payment details do not match this checkout.'
            )

        status_map = {
            'authorized': PaymentAttempt.STATUS_AUTHORIZED,
            'captured': PaymentAttempt.STATUS_CAPTURED,
            'failed': PaymentAttempt.STATUS_FAILED,
        }
        status = status_map.get(payment.get('status'))
        if status is None:
            raise PaymentValidationError(
                'Razorpay has not reported a final payment status.'
            )
        _apply_payment_status(attempt, status, payment_id)
        return attempt


def verify_checkout_payment(
    *,
    payment_attempt_id,
    customer,
    order_id,
    payment_id,
    signature,
):
    attempt = (
        PaymentAttempt.objects.select_related('checkout_attempt')
        .filter(
            pk=payment_attempt_id,
            checkout_attempt__customer=customer,
        )
        .first()
    )
    if attempt is None:
        raise PaymentWorkflowError('This payment attempt could not be found.')
    if not attempt.provider_order_id or order_id != attempt.provider_order_id:
        raise PaymentValidationError('The payment does not match this checkout.')
    if not gateway.verify_checkout_signature(
        order_id=order_id,
        payment_id=payment_id,
        signature=signature,
    ):
        raise PaymentValidationError('The payment signature is invalid.')
    payment = gateway.fetch_payment(payment_id)
    if payment.get('id') != payment_id:
        raise PaymentValidationError(
            'Razorpay returned a different payment reference.'
        )
    return _update_attempt_from_provider(
        payment_attempt_id=attempt.pk,
        payment=payment,
    )


def process_webhook(*, body, signature, event_id):
    if not event_id:
        raise PaymentValidationError('The webhook event ID is missing.')
    if not gateway.verify_webhook_signature(body=body, signature=signature):
        raise PaymentValidationError('The webhook signature is invalid.')
    try:
        event = json.loads(body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaymentValidationError('The webhook body is invalid.') from exc
    if not isinstance(event, dict) or not isinstance(event.get('event'), str):
        raise PaymentValidationError('The webhook event is invalid.')

    event_type = event['event']
    supported_statuses = {
        'payment.authorized': PaymentAttempt.STATUS_AUTHORIZED,
        'payment.captured': PaymentAttempt.STATUS_CAPTURED,
        'payment.failed': PaymentAttempt.STATUS_FAILED,
    }
    status = supported_statuses.get(event_type)
    payment = None
    if status is not None:
        try:
            payment = event['payload']['payment']['entity']
        except (KeyError, TypeError) as exc:
            raise PaymentValidationError(
                'The webhook payment details are missing.'
            ) from exc
        if not isinstance(payment, dict):
            raise PaymentValidationError('The webhook payment details are invalid.')

    with transaction.atomic():
        try:
            with transaction.atomic():
                WebhookEvent.objects.create(
                    event_id=event_id,
                    event_type=event_type,
                )
        except IntegrityError:
            if WebhookEvent.objects.filter(event_id=event_id).exists():
                return False
            raise

        if status is not None:
            initial_attempt = PaymentAttempt.objects.filter(
                provider_order_id=payment.get('order_id'),
            ).only('checkout_attempt_id').first()
            if initial_attempt is None:
                raise PaymentWorkflowError(
                    'No payment attempt matches the webhook order.'
                )
            CheckoutAttempt.objects.select_for_update().get(
                pk=initial_attempt.checkout_attempt_id,
            )
            attempt = PaymentAttempt.objects.select_for_update().get(
                pk=initial_attempt.pk,
            )
            if (
                payment.get('amount') != amount_in_subunits(attempt.amount)
                or payment.get('currency') != attempt.currency
                or not isinstance(payment.get('id'), str)
                or payment.get('status') != event_type.split('.')[-1]
            ):
                raise PaymentValidationError(
                    'The webhook payment does not match the checkout.'
                )
            _apply_payment_status(
                attempt,
                status,
                payment['id'],
            )
    return True


@transaction.atomic
def request_paid_order_cancellation(*, order_number, customer, reason):
    order = (
        Order.objects.select_for_update()
        .filter(
            order_number=order_number,
            customer=customer,
        )
        .first()
    )
    if order is None:
        raise PaymentWorkflowError('That order could not be found.')
    if (
        order.payment_status != Order.PAYMENT_PAID
        or order.status not in (Order.STATUS_PENDING, Order.STATUS_CONFIRMED)
    ):
        raise PaymentWorkflowError(
            'Only paid orders that have not started fulfillment need cancellation review.'
        )
    if OrderCancellationRequest.objects.filter(order=order).exists():
        raise PaymentWorkflowError(
            'A cancellation request already exists for this order. Contact BENI support if you need to follow up.'
        )
    cancellation = OrderCancellationRequest.objects.create(
        order=order,
        reason=reason,
    )
    notify_active_staff(
        event_key=f'order-cancellation:{cancellation.pk}:requested',
        title='Paid order cancellation review',
        message=f'Order {order.order_number} needs cancellation review.',
        destination_name='payments:cancellation_queue',
    )
    return cancellation


@transaction.atomic
def review_cancellation_request(*, request_id, reviewer, approve, notes=''):
    if not reviewer.is_active or not reviewer.is_staff:
        raise PermissionDenied
    cancellation = (
        OrderCancellationRequest.objects.select_for_update()
        .select_related('order')
        .filter(pk=request_id)
        .first()
    )
    if cancellation is None:
        raise PaymentWorkflowError('That cancellation request could not be found.')
    if cancellation.status != OrderCancellationRequest.STATUS_PENDING:
        raise PaymentWorkflowError('That cancellation request has already been reviewed.')

    if approve:
        try:
            order = transition_order(
                order_number=cancellation.order.order_number,
                actor=reviewer,
                new_status=Order.STATUS_CANCELLED,
                staff_review=True,
            )
        except OrderTransitionError as exc:
            raise PaymentWorkflowError(str(exc)) from exc
        if order is None:
            raise PaymentWorkflowError('That order could not be found.')
        cancellation.status = OrderCancellationRequest.STATUS_APPROVED
    else:
        cancellation.status = OrderCancellationRequest.STATUS_REJECTED

    cancellation.reviewer = reviewer
    cancellation.reviewer_notes = notes
    cancellation.reviewed_at = timezone.now()
    cancellation.save(
        update_fields=(
            'status',
            'reviewer',
            'reviewer_notes',
            'reviewed_at',
        )
    )
    create_notification(
        recipient=cancellation.order.customer,
        event_key=f'order-cancellation:{cancellation.pk}:{cancellation.status}',
        title='Cancellation request reviewed',
        message=(
            f'Your cancellation request for order '
            f'{cancellation.order.order_number} was '
            f'{cancellation.get_status_display().lower()}.'
        ),
        destination_name='customers:order_detail',
        destination_args=(cancellation.order.order_number,),
    )
    return cancellation
