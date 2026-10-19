import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.models import CheckoutAttempt, Order, OrderItem
from products.models import Product
from shops.models import Shop


class OrderInvoiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(
            username='invoice-customer',
            password='test-password',
        )
        self.owner = user_model.objects.create_user(
            username='invoice-shopkeeper',
            password='test-password',
        )
        self.other_user = user_model.objects.create_user(
            username='invoice-outsider',
            password='test-password',
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name='Receipt Shop',
            category='Grocery',
            phone='555-0100',
            address='1 Main Street',
            city='Test City',
            state='Test State',
            postal_code='12345',
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name='Tea',
            category='Grocery',
            price=Decimal('4.50'),
            stock_quantity=2,
        )
        self.checkout = CheckoutAttempt.objects.create(
            customer=self.customer,
            token=uuid.uuid4(),
            cart_digest='a' * 64,
        )
        self.order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            checkout_attempt=self.checkout,
            order_number='BENI-INVOICE-1',
            contact_name='Invoice Customer',
            contact_phone='555-0101',
            address_line1='2 Market Road',
            city='Test City',
            state='Test State',
            postal_code='12345',
            subtotal=Decimal('9.00'),
            delivery_fee=Decimal('1.00'),
            service_fee=Decimal('0.50'),
            total=Decimal('10.50'),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name='Tea',
            product_category='Grocery',
            unit_price=Decimal('4.50'),
            quantity=2,
            line_total=Decimal('9.00'),
        )
        self.url = reverse(
            'billing:order_invoice',
            args=(self.order.order_number,),
        )

    def test_customer_can_view_receipt_for_own_order(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BENI-INVOICE-1')
        self.assertContains(response, 'Tea')
        self.assertContains(response, '10.50')
        self.assertContains(response, 'not a tax invoice')

    def test_shop_owner_can_view_receipt_for_owned_shop_order(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Receipt Shop')
        self.assertContains(response, 'Invoice Customer')

    def test_unrelated_user_cannot_view_receipt(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])
