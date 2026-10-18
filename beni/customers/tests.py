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
        self.assertRedirects(
            response,
            reverse('catalog:detail', args=[self.product.pk]),
            fetch_redirect_response=False,
        )
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

    def test_non_customer_accounts_cannot_manage_cart_or_checkout(self):
        shopkeeper = get_user_model().objects.create_user(username='shopkeeper-cart-user')
        shopkeeper.groups.add(self.shopkeeper_group)
        self.client.force_login(shopkeeper)
        self.assertEqual(self.client.get(reverse('customers:cart')).status_code, 403)
        self.assertEqual(self.client.get(reverse('customers:checkout')).status_code, 403)

        administrator = get_user_model().objects.create_user(
            username='staff-cart-user',
            is_staff=True,
        )
        self.client.force_login(administrator)
        self.assertEqual(self.client.get(reverse('customers:cart')).status_code, 403)
        self.assertEqual(self.client.get(reverse('customers:checkout')).status_code, 403)
