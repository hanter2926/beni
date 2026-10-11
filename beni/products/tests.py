from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase
from django.urls import reverse

from shops.models import Shop

from .models import Product


class ProductModelTests(TestCase):
	def setUp(self):
		self.owner = get_user_model().objects.create_user(
			username='product-model-owner',
			password='test-password-2026!',
		)
		self.shop = self.make_shop(self.owner, 'Product model shop')

	def make_shop(self, owner, name):
		return Shop.objects.create(
			owner=owner,
			name=name,
			category='Grocery',
			phone='555-0100',
			address='10 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
		)

	def make_product(self, **overrides):
		values = {
			'shop': self.shop,
			'name': 'Tea',
			'category': 'Pantry',
			'price': Decimal('4.50'),
			'stock_quantity': 3,
		}
		values.update(overrides)
		return Product(**values)

	def test_negative_price_and_stock_fail_model_validation(self):
		for field, value in (('price', Decimal('-0.01')), ('stock_quantity', -1)):
			with self.subTest(field=field):
				product = self.make_product(**{field: value})
				with self.assertRaises(ValidationError):
					product.full_clean()

	def test_database_rejects_negative_price_and_stock(self):
		for field, value in (('price', Decimal('-0.01')), ('stock_quantity', -1)):
			with self.subTest(field=field):
				product = self.make_product(**{field: value})
				with self.assertRaises(DatabaseError):
					with transaction.atomic():
						product.save()

	def test_sku_is_unique_per_shop_and_blank_sku_is_optional(self):
		existing = self.make_product(sku='TEA-1')
		existing.save()
		duplicate = self.make_product(sku='TEA-1')
		with self.assertRaises(ValidationError):
			duplicate.full_clean()

		blank_sku_product = self.make_product(sku='   ')
		blank_sku_product.full_clean()
		blank_sku_product.save()
		self.assertIsNone(blank_sku_product.sku)


class ProductOwnershipTests(TestCase):
	password = 'BENI-test-password-2026!'

	def setUp(self):
		self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
		self.owner = self.create_shopkeeper('product-owner')
		self.other_owner = self.create_shopkeeper('other-product-owner')
		self.own_shop = self.make_shop(self.owner, 'Owner shop')
		self.other_shop = self.make_shop(self.other_owner, 'Other shop')
		self.other_product = Product.objects.create(
			shop=self.other_shop,
			name='Other product',
			category='Pantry',
			price=Decimal('2.50'),
			stock_quantity=1,
		)
		self.client.force_login(self.owner)

	def create_shopkeeper(self, username):
		user = get_user_model().objects.create_user(username=username, password=self.password)
		user.groups.add(self.shopkeeper_group)
		return user

	def make_shop(self, owner, name):
		return Shop.objects.create(
			owner=owner,
			name=name,
			category='Grocery',
			phone='555-0100',
			address='10 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
		)

	def product_data(self, shop_id, name):
		return {
			'shop': str(shop_id),
			'name': name,
			'category': 'Pantry',
			'description': '',
			'sku': '',
			'price': '4.50',
			'stock_quantity': '3',
			'is_active': 'on',
		}

	def test_create_only_accepts_shops_owned_by_user(self):
		response = self.client.post(
			reverse('products:create'),
			self.product_data(self.own_shop.pk, 'Owner product'),
		)
		self.assertRedirects(response, reverse('products:list'), fetch_redirect_response=False)
		product = Product.objects.get(name='Owner product')
		self.assertEqual(product.shop, self.own_shop)

		response = self.client.post(
			reverse('products:create'),
			self.product_data(self.other_shop.pk, 'Forged product'),
		)
		self.assertEqual(response.status_code, 200)
		self.assertFalse(Product.objects.filter(name='Forged product').exists())

	def test_list_and_update_are_scoped_to_shop_owner(self):
		own_product = Product.objects.create(
			shop=self.own_shop,
			name='Visible product',
			category='Pantry',
			price=Decimal('1.25'),
			stock_quantity=1,
		)
		response = self.client.get(reverse('products:list'))
		self.assertContains(response, 'Visible product')
		self.assertNotContains(response, 'Other product')
		self.assertEqual(
			self.client.get(reverse('products:edit', args=[self.other_product.pk])).status_code,
			404,
		)
		self.assertEqual(
			self.client.get(reverse('products:edit', args=[own_product.pk])).status_code,
			200,
		)

	def test_customer_and_anonymous_users_cannot_manage_products(self):
		self.client.logout()
		self.assertEqual(self.client.get(reverse('products:list')).status_code, 302)

		customer = get_user_model().objects.create_user(
			username='product-customer',
			password=self.password,
		)
		self.client.force_login(customer)
		self.assertEqual(self.client.get(reverse('products:create')).status_code, 403)
		self.assertEqual(
			self.client.get(reverse('products:edit', args=[self.other_product.pk])).status_code,
			403,
		)
