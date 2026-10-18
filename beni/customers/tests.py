from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from products.models import Product
from shops.models import Shop


class CustomerCartTests(TestCase):
    def setUp(self):
        self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
        self.customer = get_user_model().objects.create_user(username='customer-cart-user')
        self.shop_owner = get_user_model().objects.create_user(username='shop-cart-owner')
        self.shop_owner.groups.add(self.shopkeeper_group)
        self.shop = Shop.objects.create(
            owner=self.shop_owner,
            name='North Market',
            category='Groceries',
            phone='555-0100',
            address='1 Main St',
            city='Sample City',
            state='Sample State',
            postal_code='12345',
            is_active=True,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name='Green Tea',
            category='Tea',
            price=Decimal('4.50'),
            stock_quantity=5,
            is_active=True,
        )

    def test_customer_can_add_update_remove_cart_items(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('customers:cart_add', args=[self.product.pk]),
            {'quantity': 2},
        )
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)
        cart = self.client.session.get('beni_cart')
        self.assertEqual(cart[str(self.product.pk)]['quantity'], 2)

        response = self.client.post(
            reverse('customers:cart_update', args=[self.product.pk]),
            {'quantity': 3},
        )
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)
        cart = self.client.session.get('beni_cart')
        self.assertEqual(cart[str(self.product.pk)]['quantity'], 3)

        response = self.client.post(reverse('customers:cart_remove', args=[self.product.pk]))
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)
        self.assertNotIn(str(self.product.pk), self.client.session.get('beni_cart', {}))

    def test_cart_rejects_invalid_stock_and_price_tampering(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('customers:cart_add', args=[self.product.pk]),
            {'quantity': 99},
        )
        self.assertRedirects(response, reverse('catalog:detail', args=[self.product.pk]), fetch_redirect_response=False)
        self.assertNotIn(str(self.product.pk), self.client.session.get('beni_cart', {}))

        self.client.session['beni_cart'] = {
            str(self.product.pk): {
                'product_id': self.product.pk,
                'shop_id': self.shop.pk,
                'shop_name': self.shop.name,
                'name': self.product.name,
                'category': self.product.category,
                'quantity': 1,
                'unit_price': '99.99',
                'image': '',
            }
        }
        self.client.session.save()
        response = self.client.get(reverse('customers:checkout'))
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)

    def test_checkout_creates_order_snapshot_and_rejects_duplicate_submission(self):
        self.client.force_login(self.customer)
        session = self.client.session
        session['beni_cart'] = {
            str(self.product.pk): {
                'product_id': self.product.pk,
                'shop_id': self.shop.pk,
                'shop_name': self.shop.name,
                'name': self.product.name,
                'category': self.product.category,
                'quantity': 2,
                'unit_price': str(self.product.price),
                'image': '',
            }
        }
        session.save()

        response = self.client.post(
            reverse('customers:checkout'),
            {
                'full_name': 'Jane Customer',
                'phone': '9991112222',
                'address_line1': '14 Market Lane',
                'city': 'Sample City',
                'state': 'Sample State',
                'postal_code': '10001',
                'delivery_notes': 'Leave at front desk',
            },
        )
        self.assertEqual(response.status_code, 302)
        orders = self.client.session.get('beni_orders', [])
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]['items'][0]['quantity'], 2)

        duplicate = self.client.post(
            reverse('customers:checkout'),
            {
                'full_name': 'Jane Customer',
                'phone': '9991112222',
                'address_line1': '14 Market Lane',
                'city': 'Sample City',
                'state': 'Sample State',
                'postal_code': '10001',
                'delivery_notes': 'Leave at front desk',
            },
        )
        self.assertRedirects(duplicate, reverse('customers:orders'), fetch_redirect_response=False)

    def test_non_customer_accounts_cannot_manage_cart(self):
        shopkeeper = get_user_model().objects.create_user(username='shopkeeper-cart-user')
        shopkeeper.groups.add(self.shopkeeper_group)
        self.client.force_login(shopkeeper)
        self.assertEqual(self.client.get(reverse('customers:cart')).status_code, 403)
        self.assertEqual(self.client.get(reverse('customers:checkout')).status_code, 403)


class ShopkeeperOrderVisibilityTests(TestCase):
    def setUp(self):
        self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
        self.user = get_user_model().objects.create_user(username='shopkeeper-order-view')
        self.user.groups.add(self.shopkeeper_group)
        self.shop_one = Shop.objects.create(
            owner=self.user,
            name='Own Shop One',
            category='Grocery',
            phone='555-0101',
            address='2 Main St',
            city='Example City',
            state='Example State',
            postal_code='12345',
            is_active=True,
        )
        self.other_owner = get_user_model().objects.create_user(username='other-order-owner')
        self.other_shop = Shop.objects.create(
            owner=self.other_owner,
            name='Other Shop',
            category='Health',
            phone='555-0111',
            address='9 Side St',
            city='Example City',
            state='Example State',
            postal_code='12345',
            is_active=True,
        )

    def test_shopkeeper_only_sees_orders_from_their_own_shops(self):
        session = self.client.session
        session['beni_orders'] = [
            {
                'order_number': 'BENI-20261018-0001',
                'customer_id': 99,
                'customer_name': 'Customer One',
                'created_at': '2026-10-18T10:00:00Z',
                'status': 'pending',
                'items': [
                    {
                        'product_id': 101,
                        'shop_id': self.shop_one.pk,
                        'shop_name': self.shop_one.name,
                        'name': 'Bread',
                        'quantity': 1,
                        'unit_price': '3.50',
                        'line_total': '3.50',
                    }
                ],
                'total': '3.50',
            },
            {
                'order_number': 'BENI-20261018-0002',
                'customer_id': 99,
                'customer_name': 'Customer Two',
                'created_at': '2026-10-18T11:00:00Z',
                'status': 'pending',
                'items': [
                    {
                        'product_id': 202,
                        'shop_id': self.other_shop.pk,
                        'shop_name': self.other_shop.name,
                        'name': 'Soap',
                        'quantity': 1,
                        'unit_price': '5.00',
                        'line_total': '5.00',
                    }
                ],
                'total': '5.00',
            },
        ]
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse('shopkeeper_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'BENI-20261018-0001')
        self.assertNotContains(response, 'BENI-20261018-0002')
