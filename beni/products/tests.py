from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.forms import ImageField
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from PIL import Image

from accounts.models import Profile
from shops.models import Shop
from verification.models import VerificationApplication

from beni.upload_forms import MultipleDocumentField, MultipleImageField
from beni.upload_paths import product_gallery_image_path, verification_document_path
from beni.upload_validation import (
	MAX_VERIFICATION_DOCUMENT_SIZE,
	validate_verification_document,
)

from .forms import ProductForm
from .image_validation import (
	MAX_PRODUCT_IMAGE_PIXELS,
	MAX_PRODUCT_IMAGE_SIZE,
	validate_product_image,
)
from .models import Product


class ProductImageControlTests(SimpleTestCase):
	def test_product_image_control_uses_supported_file_types(self):
		form = ProductForm(user=get_user_model()(pk=1))
		image_input = form['image'].as_widget()

		self.assertIn('type="file"', image_input)
		self.assertIn(
			'accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"',
			image_input,
		)
		self.assertIn('product-image-preview-message', image_input)


class ProductImageValidationTests(SimpleTestCase):
	def make_image_upload(self, image_format='PNG', filename='upload.bin'):
		stream = BytesIO()
		Image.new('RGB', (20, 20), color='navy').save(stream, format=image_format)
		if filename == 'upload.bin':
			filename = {
				'JPEG': 'upload.jpg',
				'PNG': 'upload.png',
				'WEBP': 'upload.webp',
				'GIF': 'upload.gif',
			}[image_format]
		return SimpleUploadedFile(
			filename,
			stream.getvalue(),
			content_type='application/octet-stream',
		)

	def test_image_content_is_decoded_and_allowed_formats_are_accepted(self):
		for image_format in ('JPEG', 'PNG', 'WEBP'):
			with self.subTest(image_format=image_format):
				upload = ImageField().clean(self.make_image_upload(image_format))
				self.assertIs(validate_product_image(upload), upload)

	def test_unrecognized_or_malformed_content_is_rejected(self):
		gif_upload = ImageField().clean(self.make_image_upload('GIF'))
		with self.assertRaises(ValidationError):
			validate_product_image(gif_upload)

		with self.assertRaises(ValidationError):
			ImageField().clean(
				SimpleUploadedFile(
					'broken.png',
					b'not an image',
					content_type='image/png',
				)
			)
		with self.assertRaises(ValidationError):
			ImageField().clean(
				SimpleUploadedFile(
					'README.md',
					b'# Not an image',
					content_type='text/markdown',
				)
			)

	def test_file_size_and_pixel_limits_are_enforced(self):
		upload = ImageField().clean(self.make_image_upload())
		oversized = SimpleNamespace(
			size=MAX_PRODUCT_IMAGE_SIZE + 1,
			image=upload.image,
		)
		with self.assertRaisesMessage(ValidationError, '2 MB'):
			validate_product_image(oversized)

		too_many_pixels = SimpleNamespace(
			size=1,
			image=SimpleNamespace(format='JPEG', size=(5000, 5000)),
		)
		with self.assertRaisesMessage(ValidationError, '24 megapixels'):
			validate_product_image(too_many_pixels)

		too_wide = SimpleNamespace(
			size=1,
			image=SimpleNamespace(format='JPEG', size=(6001, 1)),
		)
		with self.assertRaisesMessage(ValidationError, '6000 × 6000'):
			validate_product_image(too_wide)

	def test_multiple_image_field_validates_decoded_image_content_and_count(self):
		field = MultipleImageField(
			required=False,
			max_files=2,
			max_size=2 * 1024 * 1024,
		)
		uploads = field.clean([
			self.make_image_upload('JPEG'),
			self.make_image_upload('WEBP'),
		])
		self.assertEqual(len(uploads), 2)

		with self.assertRaisesMessage(ValidationError, 'no more than 1 images'):
			MultipleImageField(
				required=False,
				max_files=1,
				max_size=2 * 1024 * 1024,
			).clean([
				self.make_image_upload('PNG'),
				self.make_image_upload('JPEG'),
			])

		with self.assertRaises(ValidationError):
			field.clean([
				SimpleUploadedFile(
					'broken.png',
					b'not an image',
					content_type='image/png',
				)
			])

	def test_verification_documents_accept_valid_pdf_and_reject_bad_content(self):
		field = MultipleDocumentField(required=False)
		pdf_upload = SimpleUploadedFile(
			'proof.pdf',
			b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF',
			content_type='application/pdf',
		)
		documents = field.clean([pdf_upload])
		self.assertEqual(len(documents), 1)
		self.assertIs(validate_verification_document(documents[0]), documents[0])

		with self.assertRaises(ValidationError):
			field.clean([
				SimpleUploadedFile(
					'fake.pdf',
					b'not a document',
					content_type='application/pdf',
				)
			])

	def test_verification_document_size_limit_is_enforced(self):
		oversized = SimpleNamespace(
			size=MAX_VERIFICATION_DOCUMENT_SIZE + 1,
			file=BytesIO(),
		)
		with self.assertRaisesMessage(ValidationError, '10 MB or smaller'):
			validate_verification_document(oversized)

	def test_upload_paths_ignore_user_filename_and_use_unique_names(self):
		upload = ImageField().clean(self.make_image_upload('PNG'))
		instance = SimpleNamespace(image=upload)
		first = product_gallery_image_path(instance, '..\\..\\private.png')
		second = product_gallery_image_path(instance, '..\\..\\private.png')
		self.assertTrue(first.startswith('products/gallery/'))
		self.assertNotIn('private', first)
		self.assertNotEqual(first, second)

	def test_verification_document_path_uses_content_not_filename_extension(self):
		pdf_upload = SimpleUploadedFile(
			'identity.jpg',
			b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF',
			content_type='image/jpeg',
		)
		document = SimpleNamespace(file=pdf_upload)
		path = verification_document_path(document, '../../identity.jpg')
		self.assertTrue(path.startswith('verification/'))
		self.assertTrue(path.endswith('.pdf'))
		self.assertNotIn('identity', path)


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
		self.assertEqual(self.client.get(reverse('products:list')).status_code, 403)
		self.assertEqual(self.client.get(reverse('products:create')).status_code, 403)
		self.assertEqual(
			self.client.get(reverse('products:edit', args=[self.other_product.pk])).status_code,
			403,
		)


class PublicProductCatalogTests(TestCase):
	@classmethod
	def setUpTestData(cls):
		owner = get_user_model().objects.create_user(username='catalog-owner')
		Profile.objects.create(
			user=owner,
			phone='+15550100005',
			phone_verified=True,
		)
		cls.active_shop = Shop.objects.create(
			owner=owner,
			name='Active Corner Shop',
			category='Grocery',
			phone='555-0100',
			address='10 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
			is_active=True,
		)
		cls.inactive_shop = Shop.objects.create(
			owner=owner,
			name='Closed Corner Shop',
			category='Grocery',
			phone='555-0101',
			address='20 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
			is_active=False,
		)
		for shop in (cls.active_shop, cls.inactive_shop):
			VerificationApplication.objects.create(
				applicant=owner,
				shop=shop,
				application_type=VerificationApplication.TYPE_SHOPKEEPER,
				status=VerificationApplication.STATUS_APPROVED,
				phone_status=VerificationApplication.CHECK_VERIFIED,
				aadhaar_status=VerificationApplication.CHECK_VERIFIED,
			)
		cls.visible_product = cls.make_product(
			cls.active_shop,
			'Green Tea',
			category='Tea',
			description='Loose leaf tea',
		)
		cls.inactive_product = cls.make_product(
			cls.active_shop,
			'Hidden Tea',
			category='Tea',
			is_active=False,
		)
		cls.product_from_inactive_shop = cls.make_product(
			cls.inactive_shop,
			'Closed Shop Tea',
			category='Tea',
		)
		cls.other_category_product = cls.make_product(
			cls.active_shop,
			'Olive Oil',
			category='Pantry',
		)

	@staticmethod
	def make_product(shop, name, category, description='', is_active=True):
		return Product.objects.create(
			shop=shop,
			name=name,
			category=category,
			description=description,
			price=Decimal('4.50'),
			stock_quantity=3,
			is_active=is_active,
		)

	def test_catalog_only_shows_active_products_from_active_shops(self):
		response = self.client.get(reverse('catalog:list'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Green Tea')
		self.assertContains(response, '4.50')
		self.assertContains(response, 'Tea')
		self.assertContains(response, 'Active Corner Shop')
		self.assertNotContains(response, 'Hidden Tea')
		self.assertNotContains(response, 'Closed Shop Tea')

	def test_search_filters_public_products_and_shop_names(self):
		response = self.client.get(reverse('catalog:list'), {'q': 'Green'})
		self.assertContains(response, 'Green Tea')
		self.assertNotContains(response, 'Olive Oil')

		response = self.client.get(reverse('catalog:list'), {'q': 'Active Corner'})
		self.assertContains(response, 'Green Tea')
		self.assertContains(response, 'Olive Oil')
		self.assertNotContains(response, 'Closed Shop Tea')

	def test_category_filter_uses_existing_product_category(self):
		response = self.client.get(reverse('catalog:list'), {'category': 'Pantry'})
		self.assertContains(response, 'Olive Oil')
		self.assertNotContains(response, 'Green Tea')
		self.assertNotContains(response, 'Hidden Tea')

	def test_detail_hides_inactive_products_and_products_from_inactive_shops(self):
		response = self.client.get(
			reverse('catalog:detail', args=[self.visible_product.pk]),
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Active Corner Shop')

		for product in (self.inactive_product, self.product_from_inactive_shop):
			with self.subTest(product=product.name):
				self.assertEqual(
					self.client.get(
						reverse('catalog:detail', args=[product.pk]),
					).status_code,
					404,
				)

	def test_signed_in_customer_can_add_available_product_from_detail(self):
		customer = get_user_model().objects.create_user(username='catalog-customer')
		self.client.force_login(customer)

		response = self.client.get(
			reverse('catalog:detail', args=[self.visible_product.pk]),
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(
			response,
			f'action="{reverse("customers:cart_add", args=[self.visible_product.pk])}"',
		)
		self.assertContains(response, 'name="quantity"')
		self.assertContains(response, 'max="3"')
		self.assertContains(response, 'Add to cart')

	def test_anonymous_customer_is_prompted_to_sign_in_before_adding(self):
		response = self.client.get(
			reverse('catalog:detail', args=[self.visible_product.pk]),
		)

		self.assertContains(response, 'Sign in to add to cart')
		self.assertContains(
			response,
			f'href="{reverse("accounts:login")}?next=/catalog/{self.visible_product.pk}/"',
		)

	def test_out_of_stock_product_has_no_add_to_cart_action(self):
		self.visible_product.stock_quantity = 0
		self.visible_product.save(update_fields=('stock_quantity',))

		response = self.client.get(
			reverse('catalog:detail', args=[self.visible_product.pk]),
		)

		self.assertContains(response, 'Currently out of stock')
		self.assertNotContains(response, 'Add to cart')

	def test_catalog_paginates_results(self):
		for index in range(13):
			self.make_product(self.active_shop, f'Paged product {index}', category='Pantry')

		first_page = self.client.get(reverse('catalog:list'))
		second_page = self.client.get(reverse('catalog:list'), {'page': 2})
		self.assertEqual(len(first_page.context['products']), 12)
		self.assertEqual(len(second_page.context['products']), 3)
