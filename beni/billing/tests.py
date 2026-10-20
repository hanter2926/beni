import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.models import CheckoutAttempt, Order, OrderItem
from payments.models import PaymentAttempt
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
        self.other_shopkeeper = user_model.objects.create_user(
            username='invoice-other-shopkeeper',
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
        self.other_shop = Shop.objects.create(
            owner=self.other_shopkeeper,
            name='Other Shop',
            category='Grocery',
            phone='555-0199',
            address='9 Other Street',
            city='Other City',
            state='Other State',
            postal_code='99999',
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
            product_sku='TEA-01',
            unit_price=Decimal('4.50'),
            quantity=2,
            line_total=Decimal('9.00'),
        )
        self.other_order = Order.objects.create(
            customer=self.customer,
            shop=self.other_shop,
            checkout_attempt=self.checkout,
            order_number='BENI-INVOICE-OTHER',
            contact_name='Invoice Customer',
            contact_phone='555-0101',
            address_line1='2 Market Road',
            city='Test City',
            state='Test State',
            postal_code='12345',
            subtotal=Decimal('0.00'),
            total=Decimal('0.00'),
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
        self.assertContains(response, 'Grocery')
        self.assertContains(response, 'SKU TEA-01')
        self.assertContains(response, '4.50')
        self.assertContains(response, '10.50')
        self.assertContains(response, '9.00')
        self.assertContains(response, '1.00')
        self.assertContains(response, '0.50')
        self.assertContains(response, 'Cash on delivery')
        self.assertContains(response, 'Not started')
        self.assertContains(response, 'Tax and discounts are not itemized')
        self.assertContains(response, 'not a tax invoice')
        self.assertNotContains(response, 'Payment reference')
        self.assertNotContains(response, 'Payment timestamp')

    def test_shop_owner_can_view_receipt_for_owned_shop_order(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Receipt Shop')
        self.assertContains(response, 'Invoice Customer')

    def test_other_shopkeeper_cannot_view_order_from_another_shop(self):
        self.client.force_login(self.other_shopkeeper)

        own_order_response = self.client.get(
            reverse(
                'billing:order_invoice',
                args=(self.other_order.order_number,),
            )
        )
        self.assertEqual(own_order_response.status_code, 200)
        self.assertContains(own_order_response, 'Other Shop')

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b'Invoice Customer', response.content)

    def test_staff_can_view_receipt(self):
        staff = get_user_model().objects.create_user(
            username='invoice-staff',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BENI-INVOICE-1')
        self.assertEqual(response.context['role_label'], 'Admin')

    def test_captured_payment_reference_is_shown_without_invented_timestamp(self):
        self.order.payment_status = Order.PAYMENT_PAID
        self.order.save(update_fields=('payment_status',))
        PaymentAttempt.objects.create(
            checkout_attempt=self.checkout,
            amount=Decimal('10.50'),
            currency='INR',
            status=PaymentAttempt.STATUS_CAPTURED,
            provider_order_id='order_provider_123',
            provider_payment_id='pay_provider_456',
        )
        self.client.force_login(self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pay_provider_456')
        self.assertContains(response, 'Payment reference')
        self.assertNotContains(response, 'order_provider_123')
        self.assertNotContains(response, 'Payment timestamp')
        self.assertNotContains(response, 'Payment date')
        self.assertNotContains(response, 'RAZORPAY_KEY_SECRET')

    def test_missing_optional_contact_and_shop_data_renders_safely(self):
        self.order.contact_phone = ''
        self.order.address_line1 = ''
        self.order.city = ''
        self.order.state = ''
        self.order.postal_code = ''
        self.order.delivery_notes = ''
        self.order.save(
            update_fields=(
                'contact_phone',
                'address_line1',
                'city',
                'state',
                'postal_code',
                'delivery_notes',
            )
        )
        self.shop.phone = ''
        self.shop.address = ''
        self.shop.city = ''
        self.shop.state = ''
        self.shop.postal_code = ''
        self.shop.save(
            update_fields=(
                'phone',
                'address',
                'city',
                'state',
                'postal_code',
            )
        )
        self.client.force_login(self.customer)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invoice Customer')
        self.assertContains(response, 'Receipt Shop')
        self.assertNotContains(response, '555-0101')
        self.assertNotContains(response, '1 Main Street')

    def test_unrelated_user_cannot_view_receipt(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response['Location'])
