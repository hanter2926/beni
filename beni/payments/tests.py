import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from django.urls import reverse

from orders.models import CheckoutAttempt, Order, OrderItem
from orders.services import (
    OrderTransitionError,
    transition_order,
    valid_status_targets,
)
from products.models import Product
from shops.models import Shop

from .gateway import PaymentProviderError
from .models import OrderCancellationRequest, PaymentAttempt, WebhookEvent
from .services import (
    PaymentValidationError,
    create_payment_attempt,
    process_webhook,
    request_paid_order_cancellation,
    review_cancellation_request,
    verify_checkout_payment,
)


@override_settings(
    RAZORPAY_KEY_ID='rzp_test_public',
    RAZORPAY_KEY_SECRET='test-key-secret',
    RAZORPAY_WEBHOOK_SECRET='test-webhook-secret',
)
class PaymentWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(username='payment-customer')
        self.owner_one = user_model.objects.create_user(username='payment-owner-one')
        self.owner_two = user_model.objects.create_user(username='payment-owner-two')
        self.staff = user_model.objects.create_user(
            username='payment-staff',
            is_staff=True,
        )
        self.shop_one = self.make_shop(self.owner_one, 'One')
        self.shop_two = self.make_shop(self.owner_two, 'Two')
        self.checkout_attempt = CheckoutAttempt.objects.create(
            customer=self.customer,
            token=uuid.uuid4(),
            cart_digest='a' * 64,
            payment_method=CheckoutAttempt.PAYMENT_METHOD_RAZORPAY,
        )
        self.order_one = self.make_order(self.shop_one, '9.00')

    def make_shop(self, owner, suffix):
        return Shop.objects.create(
            owner=owner,
            name=f'Market {suffix}',
            category='Groceries',
            phone='555-0100',
            address='1 Main St',
            city='Sample City',
            state='Sample State',
            postal_code='12345',
            is_active=True,
        )

    def make_order(self, shop, total):
        value = Decimal(total)
        return Order.objects.create(
            customer=self.customer,
            shop=shop,
            checkout_attempt=self.checkout_attempt,
            order_number=f'BENI-TEST-{uuid.uuid4().hex[:20].upper()}',
            contact_name='Jane Customer',
            contact_phone='9991112222',
            address_line1='14 Market Lane',
            city='Sample City',
            state='Sample State',
            postal_code='10001',
            subtotal=value,
            delivery_fee=Decimal('0.00'),
            service_fee=Decimal('0.00'),
            total=value,
        )

    def create_provider_attempt(self):
        amount = sum(
            Order.objects.filter(
                checkout_attempt=self.checkout_attempt,
            ).values_list('total', flat=True),
            Decimal('0.00'),
        )
        with patch(
            'payments.services.gateway.create_order',
            return_value={
                'id': 'order_beni_test',
                'amount': int(amount * 100),
                'currency': 'INR',
            },
        ) as create_order:
            attempt = create_payment_attempt(
                checkout_attempt_id=self.checkout_attempt.pk,
                customer=self.customer,
            )
        return attempt, create_order

    def checkout_signature(self, order_id, payment_id):
        return hmac.new(
            b'test-key-secret',
            f'{order_id}|{payment_id}'.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

    def webhook(self, *, event_id, event_type, payment_id='pay_beni_test'):
        body = json.dumps({
            'event': event_type,
            'payload': {
                'payment': {
                    'entity': {
                        'id': payment_id,
                        'order_id': 'order_beni_test',
                        'amount': 900,
                        'currency': 'INR',
                        'status': event_type.split('.')[-1],
                    },
                },
            },
        }).encode('utf-8')
        signature = hmac.new(
            b'test-webhook-secret',
            body,
            hashlib.sha256,
        ).hexdigest()
        return process_webhook(
            body=body,
            signature=signature,
            event_id=event_id,
        )

    def test_create_payment_attempt_uses_aggregate_checkout_total(self):
        self.make_order(self.shop_two, '3.25')
        attempt, create_order = self.create_provider_attempt()

        self.assertEqual(attempt.amount, Decimal('12.25'))
        self.assertEqual(attempt.provider_order_id, 'order_beni_test')
        create_order.assert_called_once_with(
            amount=1225,
            currency='INR',
            receipt=f'beni-{attempt.pk}',
            notes={'checkout_attempt': str(self.checkout_attempt.token)},
        )
        self.assertEqual(
            set(
                Order.objects.filter(
                    checkout_attempt=self.checkout_attempt,
                ).values_list('payment_status', flat=True)
            ),
            {Order.PAYMENT_PENDING},
        )

    def test_provider_failure_is_persisted_and_can_be_retried(self):
        with patch(
            'payments.services.gateway.create_order',
            side_effect=PaymentProviderError('temporary outage'),
        ):
            with self.assertRaises(PaymentProviderError) as raised:
                create_payment_attempt(
                    checkout_attempt_id=self.checkout_attempt.pk,
                    customer=self.customer,
                )
        self.assertEqual(str(raised.exception), 'temporary outage')
        failed = PaymentAttempt.objects.get()
        self.assertEqual(failed.status, PaymentAttempt.STATUS_FAILED)
        self.assertEqual(
            Order.objects.get(pk=self.order_one.pk).payment_status,
            Order.PAYMENT_FAILED,
        )

        with patch(
            'payments.services.gateway.create_order',
            return_value={
                'id': 'order_beni_retry',
                'amount': 900,
                'currency': 'INR',
            },
        ):
            retry = create_payment_attempt(
                checkout_attempt_id=self.checkout_attempt.pk,
                customer=self.customer,
            )
        self.assertNotEqual(retry.pk, failed.pk)
        self.assertEqual(retry.provider_order_id, 'order_beni_retry')

    def test_checkout_signature_is_not_enough_without_captured_provider_status(self):
        attempt, _ = self.create_provider_attempt()
        with patch(
            'payments.services.gateway.fetch_payment',
            return_value={
                'id': 'pay_beni_test',
                'order_id': 'order_beni_test',
                'amount': 900,
                'currency': 'INR',
                'status': 'authorized',
            },
        ):
            verified = verify_checkout_payment(
                payment_attempt_id=attempt.pk,
                customer=self.customer,
                order_id='order_beni_test',
                payment_id='pay_beni_test',
                signature=self.checkout_signature(
                    'order_beni_test',
                    'pay_beni_test',
                ),
            )

        self.assertEqual(verified.status, PaymentAttempt.STATUS_AUTHORIZED)
        self.assertEqual(
            Order.objects.get(pk=self.order_one.pk).payment_status,
            Order.PAYMENT_PENDING,
        )

    def test_invalid_checkout_signature_does_not_query_provider(self):
        attempt, _ = self.create_provider_attempt()
        with patch('payments.services.gateway.fetch_payment') as fetch_payment:
            with self.assertRaises(PaymentValidationError):
                verify_checkout_payment(
                    payment_attempt_id=attempt.pk,
                    customer=self.customer,
                    order_id='order_beni_test',
                    payment_id='pay_beni_test',
                    signature='invalid',
                )
        fetch_payment.assert_not_called()

    def test_captured_payment_callback_updates_all_orders(self):
        self.make_order(self.shop_two, '3.25')
        attempt, _ = self.create_provider_attempt()
        with patch(
            'payments.services.gateway.fetch_payment',
            return_value={
                'id': 'pay_beni_test',
                'order_id': 'order_beni_test',
                'amount': 1225,
                'currency': 'INR',
                'status': 'captured',
            },
        ):
            verified = verify_checkout_payment(
                payment_attempt_id=attempt.pk,
                customer=self.customer,
                order_id='order_beni_test',
                payment_id='pay_beni_test',
                signature=self.checkout_signature(
                    'order_beni_test',
                    'pay_beni_test',
                ),
            )

        self.assertEqual(verified.status, PaymentAttempt.STATUS_CAPTURED)
        self.assertEqual(
            set(
                Order.objects.filter(
                    checkout_attempt=self.checkout_attempt,
                ).values_list('payment_status', flat=True)
            ),
            {Order.PAYMENT_PAID},
        )

    def test_captured_webhook_is_verified_idempotent_and_order_independent(self):
        attempt, _ = self.create_provider_attempt()

        self.assertTrue(self.webhook(
            event_id='evt-captured',
            event_type='payment.captured',
        ))
        self.assertFalse(self.webhook(
            event_id='evt-captured',
            event_type='payment.captured',
        ))
        self.assertTrue(self.webhook(
            event_id='evt-authorized-late',
            event_type='payment.authorized',
        ))

        attempt.refresh_from_db()
        self.assertEqual(attempt.status, PaymentAttempt.STATUS_CAPTURED)
        self.assertEqual(attempt.provider_payment_id, 'pay_beni_test')
        self.assertEqual(
            Order.objects.get(pk=self.order_one.pk).payment_status,
            Order.PAYMENT_PAID,
        )
        self.assertEqual(WebhookEvent.objects.count(), 2)

    def test_invalid_webhook_signature_is_rejected_before_event_persistence(self):
        with self.assertRaises(PaymentValidationError):
            process_webhook(
                body=b'{"event":"payment.captured"}',
                signature='invalid',
                event_id='evt-invalid',
            )
        self.assertEqual(WebhookEvent.objects.count(), 0)

    def test_paid_cancellation_waits_for_staff_and_does_not_refund(self):
        product = Product.objects.create(
            shop=self.shop_one,
            name='Green Tea',
            category='General',
            price=Decimal('4.50'),
            stock_quantity=3,
            is_active=True,
        )
        OrderItem.objects.create(
            order=self.order_one,
            product=product,
            product_name=product.name,
            unit_price=Decimal('4.50'),
            quantity=2,
            line_total=Decimal('9.00'),
        )
        self.order_one.payment_status = Order.PAYMENT_PAID
        self.order_one.save(update_fields=('payment_status',))

        cancellation = request_paid_order_cancellation(
            order_number=self.order_one.order_number,
            customer=self.customer,
            reason='Ordered by mistake',
        )
        self.order_one.refresh_from_db()
        self.assertEqual(self.order_one.status, Order.STATUS_PENDING)
        self.assertEqual(Product.objects.get(pk=product.pk).stock_quantity, 3)
        self.assertEqual(cancellation.status, OrderCancellationRequest.STATUS_PENDING)

        reviewed = review_cancellation_request(
            request_id=cancellation.pk,
            reviewer=self.staff,
            approve=True,
            notes='Approved; process any refund manually.',
        )
        self.order_one.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(reviewed.status, OrderCancellationRequest.STATUS_APPROVED)
        self.assertEqual(self.order_one.status, Order.STATUS_CANCELLED)
        self.assertEqual(self.order_one.payment_status, Order.PAYMENT_PAID)
        self.assertEqual(product.stock_quantity, 5)

    def test_paid_order_cannot_be_cancelled_outside_staff_review(self):
        self.order_one.payment_status = Order.PAYMENT_PAID
        self.order_one.save(update_fields=('payment_status',))

        with self.assertRaises(OrderTransitionError):
            transition_order(
                order_number=self.order_one.order_number,
                actor=self.customer,
                new_status=Order.STATUS_CANCELLED,
            )
        with self.assertRaises(PermissionDenied):
            review_cancellation_request(
                request_id=1,
                reviewer=self.customer,
                approve=True,
            )

    def test_unpaid_online_order_cannot_be_cancelled_or_fulfilled(self):
        self.order_one.payment_status = Order.PAYMENT_PENDING
        self.order_one.save(update_fields=('payment_status',))

        self.assertEqual(
            valid_status_targets(
                Order.STATUS_PENDING,
                payment_status=Order.PAYMENT_PENDING,
                payment_method=CheckoutAttempt.PAYMENT_METHOD_RAZORPAY,
            ),
            [],
        )
        with self.assertRaises(OrderTransitionError):
            transition_order(
                order_number=self.order_one.order_number,
                actor=self.owner_one,
                new_status=Order.STATUS_CONFIRMED,
                shopkeeper=True,
            )
        with self.assertRaises(OrderTransitionError):
            transition_order(
                order_number=self.order_one.order_number,
                actor=self.customer,
                new_status=Order.STATUS_CANCELLED,
            )

    def test_staff_can_open_paid_cancellation_review_queue(self):
        self.order_one.payment_status = Order.PAYMENT_PAID
        self.order_one.save(update_fields=('payment_status',))
        request_paid_order_cancellation(
            order_number=self.order_one.order_number,
            customer=self.customer,
            reason='Please review this order.',
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse('payments:cancellation_queue'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order_one.order_number)
        self.assertContains(response, 'Approve cancellation')

    def test_customer_cannot_access_another_customers_payment_attempt(self):
        attempt, _ = self.create_provider_attempt()
        other_customer = get_user_model().objects.create_user(
            username='other-payment-customer',
        )
        self.client.force_login(other_customer)

        response = self.client.get(
            reverse(
                'payments:attempt',
                args=[attempt.pk],
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_customer_can_recover_checkout_if_payment_attempt_was_not_created(self):
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse(
                'customers:order_detail',
                args=[self.order_one.order_number],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Start online payment')
        self.assertContains(
            response,
            reverse(
                'payments:start',
                args=[self.checkout_attempt.pk],
            ),
        )
