from io import BytesIO
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from notifications.models import Notification
from .models import Shop, ShopBankDetails, ShopPhoto
from verification.models import VerificationApplication


class ShopModelTests(TestCase):
	def setUp(self):
		self.owner = get_user_model().objects.create_user(
			username='shop-model-owner',
			password='test-password-2026!',
		)

	def make_shop(self, **overrides):
		values = {
			'owner': self.owner,
			'name': 'North Market',
			'category': 'Grocery',
			'phone': '555-0100',
			'address': '10 Main Street',
			'city': 'Example City',
			'state': 'Example State',
			'postal_code': '12345',
		}
		values.update(overrides)
		return Shop(**values)

	def test_coordinate_validation_rejects_out_of_range_values(self):
		for field, value in (('latitude', Decimal('91')), ('longitude', Decimal('-181'))):
			with self.subTest(field=field):
				shop = self.make_shop(**{field: value})
				with self.assertRaises(ValidationError):
					shop.full_clean()

	def test_database_rejects_out_of_range_coordinates(self):
		shop = self.make_shop(latitude=Decimal('91'))
		with self.assertRaises(IntegrityError):
			with transaction.atomic():
				shop.save()


class ShopOwnershipTests(TestCase):
	password = 'BENI-test-password-2026!'

	def setUp(self):
		self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
		self.owner = self.create_shopkeeper('shop-owner')
		self.other_owner = self.create_shopkeeper('other-shop-owner')
		self.own_shop = self.make_shop(self.owner, 'Owner shop')
		self.other_shop = self.make_shop(self.other_owner, 'Other shop')
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

	def shop_data(self, name):
		return {
			'name': name,
			'category': 'Grocery',
			'description': '',
			'phone': '555-0100',
			'address': '10 Main Street',
			'city': 'Example City',
			'state': 'Example State',
			'postal_code': '12345',
			'latitude': '',
			'longitude': '',
			'opening_hours': '',
			'is_active': 'on',
		}

	def test_create_assigns_signed_in_user_as_owner(self):
		response = self.client.post(
			reverse('shops:create'),
			self.shop_data('New shop'),
		)

		shop = Shop.objects.get(name='New shop')
		self.assertRedirects(
			response,
			reverse('verification:shopkeeper_application', args=[shop.pk]),
			fetch_redirect_response=False,
		)
		self.assertEqual(shop.owner, self.owner)
		self.assertFalse(shop.is_active)
		self.assertFalse(
			VerificationApplication.objects.filter(shop=shop).exists()
		)

	def test_list_and_edit_are_scoped_to_owner(self):
		response = self.client.get(reverse('shops:list'))
		self.assertContains(response, 'Owner shop')
		self.assertNotContains(response, 'Other shop')
		self.assertEqual(
			self.client.get(reverse('shops:edit', args=[self.other_shop.pk])).status_code,
			404,
		)

	def test_foreign_shop_post_cannot_update_shop(self):
		response = self.client.post(
			reverse('shops:edit', args=[self.other_shop.pk]),
			self.shop_data('Changed by another owner'),
		)
		self.assertEqual(response.status_code, 404)
		self.other_shop.refresh_from_db()
		self.assertEqual(self.other_shop.name, 'Other shop')

	def test_shop_owner_can_manage_gallery_photos(self):
		buffer = BytesIO()
		Image.new('RGB', (20, 20), color='navy').save(buffer, format='PNG')
		upload = SimpleUploadedFile(
			'front.png',
			buffer.getvalue(),
			content_type='image/png',
		)
		data = self.shop_data('Photo shop')
		data['gallery_images'] = upload

		with tempfile.TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(reverse('shops:create'), data)

		self.assertEqual(response.status_code, 302)
		shop = Shop.objects.get(name='Photo shop')
		photo = ShopPhoto.objects.get(shop=shop)
		self.assertTrue(photo.image.name.startswith('shops/gallery/'))
		self.assertNotIn('front.png', photo.image.name)

	def test_shop_owner_can_save_bank_details_without_rendering_account_number(self):
		response = self.client.post(
			reverse('shops:edit', args=[self.own_shop.pk]),
			{
				**self.shop_data('Owner shop'),
				'account_holder_name': 'Shop Owner',
				'account_number': '123456789012',
				'ifsc_code': 'HDFC0001234',
			},
		)

		self.assertRedirects(
			response,
			reverse('shops:list'),
			fetch_redirect_response=False,
		)
		details = ShopBankDetails.objects.get(shop=self.own_shop)
		self.assertEqual(details.account_holder_name, 'Shop Owner')
		self.assertEqual(details.account_number, '123456789012')
		self.assertEqual(details.ifsc_code, 'HDFC0001234')
		self.assertNotContains(
			self.client.get(reverse('shops:edit', args=[self.own_shop.pk])),
			'123456789012',
		)

	def test_invalid_bank_details_are_not_saved(self):
		response = self.client.post(
			reverse('shops:edit', args=[self.own_shop.pk]),
			{
				**self.shop_data('Owner shop'),
				'account_holder_name': 'Shop Owner',
				'account_number': '123456789012',
				'ifsc_code': 'not-valid',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Enter a valid 11-character IFSC code.')
		self.assertFalse(ShopBankDetails.objects.filter(shop=self.own_shop).exists())

	def test_identity_change_on_approved_shop_suspends_listing_for_staff_review(self):
		application = VerificationApplication.objects.create(
			applicant=self.owner,
			shop=self.own_shop,
			application_type=VerificationApplication.TYPE_SHOPKEEPER,
			status=VerificationApplication.STATUS_APPROVED,
			phone_status=VerificationApplication.CHECK_VERIFIED,
			aadhaar_status=VerificationApplication.CHECK_VERIFIED,
		)
		self.own_shop.is_active = True
		self.own_shop.save(update_fields=('is_active',))
		staff = get_user_model().objects.create_user(
			username='shop-details-review-staff',
			is_staff=True,
		)

		response = self.client.post(
			reverse('shops:edit', args=[self.own_shop.pk]),
			self.shop_data('Updated owner shop'),
		)

		self.assertRedirects(
			response,
			reverse('shops:list'),
			fetch_redirect_response=False,
		)
		application.refresh_from_db()
		self.own_shop.refresh_from_db()
		self.assertEqual(application.status, VerificationApplication.STATUS_PENDING)
		self.assertFalse(self.own_shop.is_active)
		self.assertTrue(
			Notification.objects.filter(
				recipient=staff,
				title='Updated shop details need review',
			).exists()
		)

	def test_customer_and_anonymous_users_cannot_manage_shops(self):
		self.client.logout()
		self.assertEqual(self.client.get(reverse('shops:create')).status_code, 302)

		customer = get_user_model().objects.create_user(
			username='shop-customer',
			password=self.password,
		)
		self.client.force_login(customer)
		self.assertEqual(self.client.get(reverse('shops:create')).status_code, 403)
		self.assertEqual(
			self.client.get(reverse('shops:edit', args=[self.own_shop.pk])).status_code,
			403,
		)
