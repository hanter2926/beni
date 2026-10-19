from decimal import Decimal
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from products.models import Product
from shops.models import Shop
from customers.views import CART_OWNER_SESSION_KEY
from notifications.models import Notification
from payments.models import PaymentAttempt
from verification.models import VerificationApplication

from .models import CheckoutAttempt, Order, OrderItem
from .services import (
    CheckoutError,
    OrderTransitionError,
    create_orders,
    transition_order,
)


class OrdersWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
        self.customer = user_model.objects.create_user(username='order-customer')
        self.owner_one = user_model.objects.create_user(username='order-owner-one')
        self.owner_one.groups.add(self.shopkeeper_group)
        self.owner_two = user_model.objects.create_user(username='order-owner-two')
        self.owner_two.groups.add(self.shopkeeper_group)
        self.shop_one = self.make_shop(self.owner_one, 'One')
        self.shop_two = self.make_shop(self.owner_two, 'Two')
        self.make_shopkeeper_verification(self.owner_one, self.shop_one)
        self.make_shopkeeper_verification(self.owner_two, self.shop_two)
        self.product_one = self.make_product(self.shop_one, 'Green Tea', '4.50', 5)
        self.product_two = self.make_product(self.shop_two, 'Soap', '3.25', 4)

    def make_shopkeeper_verification(self, owner, shop, **overrides):
        values = {
            'applicant': owner,
            'shop': shop,
            'application_type': VerificationApplication.TYPE_SHOPKEEPER,
            'status': VerificationApplication.STATUS_APPROVED,
            'phone_status': VerificationApplication.CHECK_VERIFIED,
            'aadhaar_status': VerificationApplication.CHECK_VERIFIED,
        }
        values.update(overrides)
        return VerificationApplication.objects.create(**values)

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

    def make_product(self, shop, name, price, stock):
        return Product.objects.create(
            shop=shop,
            name=name,
            category='General',
            price=Decimal(price),
            stock_quantity=stock,
            is_active=True,
        )

    def cart_for(self, *lines):
        cart = {}
        for product, quantity in lines:
            cart[str(product.pk)] = {
                'product_id': product.pk,
                'shop_id': product.shop_id,
                'name': product.name,
                'quantity': quantity,
                'unit_price': str(product.price),
            }
        return cart

    def contact(self):
        return {
            'full_name': 'Jane Customer',
            'phone': '9991112222',
            'address_line1': '14 Market Lane',
            'city': 'Sample City',
            'state': 'Sample State',
            'postal_code': '10001',
            'delivery_notes': 'Leave at front desk',
        }

    def begin_checkout(self, cart=None):
        self.client.force_login(self.customer)
        session = self.client.session
        session['beni_cart'] = cart or self.cart_for(
            (self.product_one, 2),
            (self.product_two, 1),
        )
        session[CART_OWNER_SESSION_KEY] = str(self.customer.pk)
        session.save()
        response = self.client.get(reverse('customers:checkout'))
        self.assertEqual(response.status_code, 200)
        return response.context['checkout_token']

    def submit_checkout(self, token, contact=None):
        data = dict(contact or self.contact())
        data['checkout_token'] = str(token)
        return self.client.post(reverse('customers:checkout'), data)

    def test_multi_shop_checkout_creates_independent_orders_and_snapshots(self):
        token = self.begin_checkout()
        data = self.contact()
        data.update({'total': '0.01', 'subtotal': '0.01', 'payment_status': Order.PAYMENT_PAID})
        response = self.submit_checkout(token, data)
        self.assertEqual(response.status_code, 302)

        orders = list(Order.objects.order_by('shop_id'))
        self.assertEqual(len(orders), 2)
        self.assertEqual({order.shop_id for order in orders}, {self.shop_one.pk, self.shop_two.pk})
        self.assertEqual(orders[0].total, Decimal('9.00'))
        self.assertEqual(orders[1].total, Decimal('3.25'))
        self.assertEqual(orders[0].payment_status, Order.PAYMENT_NOT_STARTED)
        self.assertEqual(OrderItem.objects.count(), 2)
        self.assertEqual(self.product_one.__class__.objects.get(pk=self.product_one.pk).stock_quantity, 3)
        self.assertEqual(self.product_two.__class__.objects.get(pk=self.product_two.pk).stock_quantity, 3)

        item = OrderItem.objects.get(product=self.product_one)
        self.product_one.name = 'Renamed Tea'
        self.product_one.price = Decimal('7.00')
        self.product_one.save()
        item.refresh_from_db()
        self.assertEqual(item.product_name, 'Green Tea')
        self.assertEqual(item.unit_price, Decimal('4.50'))
        self.assertEqual(item.line_total, Decimal('9.00'))

    def test_repeat_submission_returns_the_existing_orders(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        first = self.submit_checkout(token)
        self.assertEqual(first.status_code, 302)
        first_order = Order.objects.get()
        second = self.submit_checkout(token)
        self.assertRedirects(
            second,
            reverse('customers:order_detail', args=[first_order.order_number]),
            fetch_redirect_response=False,
        )
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 4)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.customer,
                event_key=f'order:{first_order.pk}:placed:customer',
            ).count(),
            1,
        )

    @override_settings(
        RAZORPAY_KEY_ID='rzp_test_public',
        RAZORPAY_KEY_SECRET='test-key-secret',
        RAZORPAY_WEBHOOK_SECRET='test-webhook-secret',
    )
    def test_online_checkout_creates_one_aggregate_payment_attempt(self):
        token = self.begin_checkout()
        data = self.contact()
        data['payment_method'] = 'razorpay'
        with patch(
            'payments.services.gateway.create_order',
            return_value={
                'id': 'order_checkout_test',
                'amount': 1225,
                'currency': 'INR',
            },
        ) as create_order:
            response = self.submit_checkout(token, data)

        payment_attempt = PaymentAttempt.objects.get()
        self.assertRedirects(
            response,
            reverse('payments:attempt', args=[payment_attempt.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(payment_attempt.amount, Decimal('12.25'))
        self.assertEqual(payment_attempt.provider_order_id, 'order_checkout_test')
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(
            set(Order.objects.values_list('payment_status', flat=True)),
            {Order.PAYMENT_PENDING},
        )
        create_order.assert_called_once()
        payment_page = self.client.get(
            reverse('payments:attempt', args=[payment_attempt.pk]),
        )
        self.assertEqual(payment_page.status_code, 200)
        self.assertContains(payment_page, 'Pay now')

    def test_online_checkout_without_provider_configuration_creates_no_orders(self):
        token = self.begin_checkout()
        data = self.contact()
        data['payment_method'] = 'razorpay'
        with override_settings(
            RAZORPAY_KEY_ID='',
            RAZORPAY_KEY_SECRET='',
            RAZORPAY_WEBHOOK_SECRET='',
        ):
            response = self.submit_checkout(token, data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Online payments are not configured')
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(PaymentAttempt.objects.count(), 0)
        self.assertEqual(
            Product.objects.get(pk=self.product_one.pk).stock_quantity,
            5,
        )

    def test_order_creation_notifies_customer_and_each_shopkeeper(self):
        token = uuid.uuid4()
        _, orders, replayed = create_orders(
            customer=self.customer,
            cart=self.cart_for(
                (self.product_one, 1),
                (self.product_two, 1),
            ),
            token=token,
            contact=self.contact(),
        )

        self.assertFalse(replayed)
        self.assertEqual(len(orders), 2)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.customer,
                title='Order placed',
            ).count(),
            2,
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner_one,
                title='New shop order',
                destination_url__contains=orders[0].order_number,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner_two,
                title='New shop order',
                destination_url__contains=orders[1].order_number,
            ).exists()
        )

    def test_order_transition_rolls_back_when_notification_persistence_fails(self):
        _, orders, _ = create_orders(
            customer=self.customer,
            cart=self.cart_for((self.product_one, 1)),
            token=uuid.uuid4(),
            contact=self.contact(),
        )
        order = orders[0]

        with patch(
            'orders.services.create_notification',
            side_effect=RuntimeError('notification persistence failed'),
        ):
            with self.assertRaises(RuntimeError):
                transition_order(
                    order_number=order.order_number,
                    actor=self.owner_one,
                    new_status=Order.STATUS_CONFIRMED,
                    shopkeeper=True,
                )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)

    def test_stale_or_tampered_cart_price_is_rejected_without_stock_change(self):
        cart = self.cart_for((self.product_one, 1))
        token = self.begin_checkout(cart)
        self.product_one.price = Decimal('5.00')
        self.product_one.save(update_fields=('price',))
        response = self.submit_checkout(token)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'price changed')
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 5)

    def test_stock_validation_prevents_checkout(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        self.product_one.stock_quantity = 0
        self.product_one.save(update_fields=('stock_quantity',))
        response = self.submit_checkout(token)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Only 0 Green Tea')
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(CheckoutAttempt.objects.count(), 0)
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 0)
        self.assertEqual(self.client.session['beni_cart'][str(self.product_one.pk)]['quantity'], 1)

    def test_inactive_products_and_shops_cannot_be_ordered(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        self.shop_one.is_active = False
        self.shop_one.save(update_fields=('is_active',))
        response = self.submit_checkout(token)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer available')
        self.assertEqual(Order.objects.count(), 0)

        self.shop_one.is_active = True
        self.shop_one.save(update_fields=('is_active',))
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        self.product_one.is_active = False
        self.product_one.save(update_fields=('is_active',))
        response = self.submit_checkout(token)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer available')
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_contact_information_is_rejected(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        contact = self.contact()
        contact['phone'] = '123 456'
        response = self.submit_checkout(token, contact)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '7 to 15 digits')
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_clears_cart_and_rejects_token_from_another_owner(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        other_customer = get_user_model().objects.create_user(
            username='checkout-cart-owner',
        )
        session = self.client.session
        session[CART_OWNER_SESSION_KEY] = str(other_customer.pk)
        session['beni_checkout_receipts'] = {
            str(token): 'old-cart-digest',
        }
        session.save()

        response = self.submit_checkout(token)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cart changed')
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(
            Product.objects.get(pk=self.product_one.pk).stock_quantity,
            5,
        )
        session = self.client.session
        self.assertEqual(session['beni_cart'], {})
        self.assertEqual(session[CART_OWNER_SESSION_KEY], str(self.customer.pk))
        self.assertNotIn('beni_checkout_receipts', session)

    def test_checkout_rejects_shop_that_becomes_ineligible_after_carting(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        verification = VerificationApplication.objects.get(shop=self.shop_one)
        verification.status = VerificationApplication.STATUS_REJECTED
        verification.save(update_fields=('status',))

        response = self.submit_checkout(token)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer available from its shop')
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(
            Product.objects.get(pk=self.product_one.pk).stock_quantity,
            5,
        )

    def test_failure_during_second_shop_rolls_back_all_orders_and_stock(self):
        cart = self.cart_for((self.product_one, 1), (self.product_two, 1))
        token = uuid.uuid4()
        real_bulk_create = OrderItem.objects.bulk_create
        calls = 0

        def fail_on_second_insert(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError('simulated item persistence failure')
            return real_bulk_create(*args, **kwargs)

        with patch('orders.services.OrderItem.objects.bulk_create', side_effect=fail_on_second_insert):
            with self.assertRaises(RuntimeError):
                create_orders(
                    customer=self.customer,
                    cart=cart,
                    token=token,
                    contact=self.contact(),
                )

        self.assertEqual(CheckoutAttempt.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 5)
        self.assertEqual(Product.objects.get(pk=self.product_two.pk).stock_quantity, 4)

        _, orders, replayed = create_orders(
            customer=self.customer,
            cart=cart,
            token=token,
            contact=self.contact(),
        )
        self.assertFalse(replayed)
        self.assertEqual(len(orders), 2)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)

    def test_cancel_restores_inventory_once_and_rejects_after_fulfillment(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 2)))
        self.submit_checkout(token)
        order = Order.objects.get()
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 3)

        self.client.post(reverse('customers:order_cancel', args=[order.order_number]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 5)
        self.client.post(reverse('customers:order_cancel', args=[order.order_number]))
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 5)

        order.status = Order.STATUS_PROCESSING
        order.save(update_fields=('status',))
        with self.assertRaises(OrderTransitionError):
            transition_order(
                order_number=order.order_number,
                actor=self.customer,
                new_status=Order.STATUS_CANCELLED,
            )
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 5)

    def test_cash_on_delivery_is_paid_when_shopkeeper_marks_delivered(self):
        _, orders, _ = create_orders(
            customer=self.customer,
            cart=self.cart_for((self.product_one, 1)),
            token=uuid.uuid4(),
            contact=self.contact(),
        )
        order = orders[0]
        for status in (
            Order.STATUS_CONFIRMED,
            Order.STATUS_PROCESSING,
            Order.STATUS_READY_FOR_PICKUP,
            Order.STATUS_OUT_FOR_DELIVERY,
            Order.STATUS_DELIVERED,
        ):
            transition_order(
                order_number=order.order_number,
                actor=self.owner_one,
                new_status=status,
                shopkeeper=True,
            )

        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_DELIVERED)
        self.assertEqual(order.payment_status, Order.PAYMENT_PAID)

    def test_customer_and_shopkeeper_access_is_object_scoped(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        self.submit_checkout(token)
        order = Order.objects.get()

        other_customer = get_user_model().objects.create_user(username='other-customer')
        self.client.force_login(other_customer)
        self.assertEqual(
            self.client.get(reverse('customers:order_detail', args=[order.order_number])).status_code,
            404,
        )

        self.client.force_login(self.owner_two)
        listing = self.client.get(reverse('shopkeeper_orders'))
        self.assertEqual(listing.status_code, 200)
        self.assertNotContains(listing, order.order_number)
        update = self.client.post(
            reverse('shopkeeper_order_update', args=[order.order_number]),
            {'status': Order.STATUS_CONFIRMED},
        )
        self.assertEqual(update.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)

        self.client.force_login(self.customer)
        customer_detail = self.client.get(
            reverse('customers:order_detail', args=[order.order_number])
        )
        self.assertContains(customer_detail, '14 Market Lane')

        self.client.force_login(self.owner_one)
        own_listing = self.client.get(reverse('shopkeeper_orders'))
        self.assertContains(own_listing, order.order_number)
        self.assertContains(own_listing, '14 Market Lane')
        update = self.client.post(
            reverse('shopkeeper_order_update', args=[order.order_number]),
            {'status': Order.STATUS_CONFIRMED},
        )
        self.assertEqual(update.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CONFIRMED)

    def test_shopkeeper_order_detail_is_scoped_to_owned_shops(self):
        token = self.begin_checkout(self.cart_for(
            (self.product_one, 1),
            (self.product_two, 1),
        ))
        self.submit_checkout(token)
        order_one = Order.objects.get(shop=self.shop_one)
        order_two = Order.objects.get(shop=self.shop_two)

        self.client.force_login(self.owner_one)
        own_detail = self.client.get(
            reverse('shopkeeper_order_detail', args=[order_one.order_number])
        )
        self.assertEqual(own_detail.status_code, 200)
        self.assertContains(own_detail, self.product_one.name)
        self.assertNotContains(own_detail, self.product_two.name)
        self.assertContains(own_detail, 'Accept order')
        self.assertContains(own_detail, 'Reject order')
        self.assertEqual(
            self.client.get(
                reverse('shopkeeper_order_detail', args=[order_two.order_number])
            ).status_code,
            404,
        )

        self.client.force_login(self.owner_two)
        other_detail = self.client.get(
            reverse('shopkeeper_order_detail', args=[order_two.order_number])
        )
        self.assertEqual(other_detail.status_code, 200)
        self.assertContains(other_detail, self.product_two.name)
        self.assertNotContains(other_detail, self.product_one.name)
        self.assertEqual(
            self.client.get(
                reverse('shopkeeper_order_detail', args=[order_one.order_number])
            ).status_code,
            404,
        )

    def test_shopkeeper_rejection_restores_only_its_order_stock_once(self):
        token = self.begin_checkout(self.cart_for(
            (self.product_one, 2),
            (self.product_two, 1),
        ))
        self.submit_checkout(token)
        order_one = Order.objects.get(shop=self.shop_one)

        self.client.force_login(self.owner_one)
        response = self.client.post(
            reverse('shopkeeper_order_update', args=[order_one.order_number]),
            {'status': Order.STATUS_CANCELLED},
        )

        self.assertRedirects(
            response,
            reverse('shopkeeper_orders'),
            fetch_redirect_response=False,
        )
        order_one.refresh_from_db()
        self.assertEqual(order_one.status, Order.STATUS_CANCELLED)
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 5)
        self.assertEqual(Product.objects.get(pk=self.product_two.pk).stock_quantity, 3)

        self.client.post(
            reverse('shopkeeper_order_update', args=[order_one.order_number]),
            {'status': Order.STATUS_CANCELLED},
        )
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).stock_quantity, 5)
        self.assertEqual(Product.objects.get(pk=self.product_two.pk).stock_quantity, 3)

    def test_shopkeeper_confirmed_order_actions_are_contextual(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        self.submit_checkout(token)
        order = Order.objects.get()

        self.client.force_login(self.owner_one)
        response = self.client.post(
            reverse('shopkeeper_order_update', args=[order.order_number]),
            {'status': Order.STATUS_CONFIRMED},
        )
        self.assertRedirects(
            response,
            reverse('shopkeeper_orders'),
            fetch_redirect_response=False,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CONFIRMED)

        detail = self.client.get(
            reverse('shopkeeper_order_detail', args=[order.order_number])
        )
        self.assertContains(detail, 'Cancel order')
        self.assertContains(detail, 'Processing')
        self.assertNotContains(detail, 'Reject order')

    def test_csrf_is_required_for_checkout_and_cancellation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.customer)
        session = client.session
        session['beni_cart'] = self.cart_for((self.product_one, 1))
        session[CART_OWNER_SESSION_KEY] = str(self.customer.pk)
        session.save()
        page = client.get(reverse('customers:checkout'))
        token = page.context['checkout_token']
        response = client.post(
            reverse('customers:checkout'),
            {'checkout_token': token, **self.contact()},
        )
        self.assertEqual(response.status_code, 403)

        _, orders, _ = create_orders(
            customer=self.customer,
            cart=self.cart_for((self.product_two, 1)),
            token=uuid.uuid4(),
            contact=self.contact(),
        )
        response = client.post(
            reverse('customers:order_cancel', args=[orders[0].order_number]),
        )
        self.assertEqual(response.status_code, 403)

        _, shop_orders, _ = create_orders(
            customer=self.customer,
            cart=self.cart_for((self.product_one, 1)),
            token=uuid.uuid4(),
            contact=self.contact(),
        )
        client.force_login(self.owner_one)
        response = client.post(
            reverse('shopkeeper_order_update', args=[shop_orders[0].order_number]),
            {'status': Order.STATUS_CONFIRMED},
        )
        self.assertEqual(response.status_code, 403)

    def test_order_history_protects_historical_product_and_shop(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        self.submit_checkout(token)
        with self.assertRaises(ProtectedError):
            self.product_one.delete()
        with self.assertRaises(ProtectedError):
            self.shop_one.delete()

    def test_product_with_order_history_cannot_be_moved_to_another_shop(self):
        token = self.begin_checkout(self.cart_for((self.product_one, 1)))
        self.submit_checkout(token)
        product = Product.objects.get(pk=self.product_one.pk)
        product.shop = self.shop_two
        with self.assertRaises(ValidationError):
            product.save()
        self.assertEqual(Product.objects.get(pk=self.product_one.pk).shop_id, self.shop_one.pk)
