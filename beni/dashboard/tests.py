from types import SimpleNamespace
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.test.client import RequestFactory

from accounts.models import Profile
from orders.models import CheckoutAttempt, Order, OrderItem
from products.models import Product
from shops.models import Shop
from verification.models import VerificationApplication


class DashboardRouteTests(TestCase):
	def test_dashboard_routes_require_authentication(self):
		for route_name in (
			'dashboard:customer',
			'dashboard:shopkeeper',
			'dashboard:repair_worker',
			'dashboard:admin',
		):
			with self.subTest(route=route_name):
				response = self.client.get(reverse(route_name))
				self.assertEqual(response.status_code, 302)

	def test_existing_admin_route_is_unchanged(self):
		self.assertEqual(reverse('admin:index'), '/admin/')

	def test_all_role_templates_render(self):
		request = RequestFactory().get('/')
		request.user = SimpleNamespace(
			is_authenticated=False,
			is_staff=True,
			get_username=lambda: 'preview-user',
		)
		request._messages = []

		for template_name in (
			'customer/dashboard.html',
			'shopkeeper/dashboard.html',
			'repair_worker/dashboard.html',
			'admin_panel/dashboard.html',
		):
			with self.subTest(template=template_name):
				content = render_to_string(
					template_name,
					{'role_label': 'Preview'},
					request=request,
				)
				self.assertIn('BENI', content)

	def test_customer_dashboard_links_to_order_history(self):
		content = render_to_string(
			'customer/dashboard.html',
			{'role_label': 'Customer'},
		)

		self.assertIn(reverse('customers:orders'), content)
		self.assertIn('View order history', content)

	def test_customer_space_uses_only_marketable_products_and_own_orders(self):
		user_model = get_user_model()
		customer = user_model.objects.create_user(username='space-customer')
		other_customer = user_model.objects.create_user(
			username='space-other-customer',
		)
		owner = user_model.objects.create_user(username='space-shop-owner')
		shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
		owner.groups.add(shopkeeper_group)
		Profile.objects.create(
			user=owner,
			phone='+15550100006',
			phone_verified=True,
		)
		shop = Shop.objects.create(
			owner=owner,
			name='Active Local Shop',
			category='Home',
			phone='555-0100',
			address='1 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
			is_active=True,
		)
		VerificationApplication.objects.create(
			applicant=owner,
			shop=shop,
			application_type=VerificationApplication.TYPE_SHOPKEEPER,
			status=VerificationApplication.STATUS_APPROVED,
			phone_status=VerificationApplication.CHECK_VERIFIED,
			aadhaar_status=VerificationApplication.CHECK_VERIFIED,
		)
		product = Product.objects.create(
			shop=shop,
			name='Real Active Product',
			category='Home',
			price=Decimal('12.50'),
			stock_quantity=3,
			is_active=True,
		)
		attempt = CheckoutAttempt.objects.create(
			customer=customer,
			token=uuid.uuid4(),
			cart_digest='a' * 64,
		)
		order = Order.objects.create(
			customer=customer,
			shop=shop,
			checkout_attempt=attempt,
			order_number='BENI-SPACE-CUSTOMER',
			contact_name='Space Customer',
			contact_phone='555-0199',
			address_line1='1 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
			subtotal=Decimal('12.50'),
			total=Decimal('12.50'),
		)
		OrderItem.objects.create(
			order=order,
			product=product,
			product_name=product.name,
			product_category=product.category,
			unit_price=product.price,
			quantity=1,
			line_total=product.price,
		)
		other_attempt = CheckoutAttempt.objects.create(
			customer=other_customer,
			token=uuid.uuid4(),
			cart_digest='b' * 64,
		)
		Order.objects.create(
			customer=other_customer,
			shop=shop,
			checkout_attempt=other_attempt,
			order_number='BENI-SPACE-OTHER',
			contact_name='Other Customer',
			contact_phone='555-0188',
			address_line1='2 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
		)
		self.client.force_login(customer)

		response = self.client.get(reverse('dashboard:customer'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Real Active Product')
		self.assertContains(response, 'Active Local Shop')
		self.assertContains(response, 'BENI-SPACE-CUSTOMER')
		self.assertNotContains(response, 'BENI-SPACE-OTHER')
		self.assertContains(response, 'Available · 3 in stock')
		self.assertContains(response, reverse('customers:cart_add', args=[product.pk]))

	def test_shopkeeper_order_pages_are_linked_from_navigation_and_dashboard(self):
		management_nav = render_to_string(
			'shopkeeper/_management_nav.html',
			{'active_nav': 'orders'},
		)
		dashboard = render_to_string(
			'shopkeeper/dashboard.html',
			{'role_label': 'Shopkeeper'},
		)
		order_url = reverse('shopkeeper_orders')

		self.assertIn(order_url, management_nav)
		self.assertIn(order_url, dashboard)
		self.assertIn('Open orders', dashboard)

	def test_shopkeeper_dashboard_shows_owned_shop_verification_and_live_counts(self):
		shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
		owner = get_user_model().objects.create_user(username='dashboard-shop-owner')
		owner.groups.add(shopkeeper_group)
		other_owner = get_user_model().objects.create_user(
			username='dashboard-other-owner',
		)
		shop = Shop.objects.create(
			owner=owner,
			name='Dashboard Shop',
			category='Grocery',
			phone='555-0100',
			address='1 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
			is_active=False,
		)
		VerificationApplication.objects.create(
			applicant=owner,
			shop=shop,
			application_type=VerificationApplication.TYPE_SHOPKEEPER,
		)
		Product.objects.create(
			shop=shop,
			name='Active item',
			category='Grocery',
			price=Decimal('10.00'),
			stock_quantity=2,
			is_active=True,
		)
		Product.objects.create(
			shop=shop,
			name='Inactive item',
			category='Grocery',
			price=Decimal('15.00'),
			stock_quantity=1,
			is_active=False,
		)
		other_shop = Shop.objects.create(
			owner=other_owner,
			name='Private Other Shop',
			category='Grocery',
			phone='555-0101',
			address='2 Main Street',
			city='Example City',
			state='Example State',
			postal_code='12345',
		)
		Product.objects.create(
			shop=other_shop,
			name='Other owner item',
			category='Grocery',
			price=Decimal('25.00'),
			stock_quantity=1,
		)
		self.client.force_login(owner)

		response = self.client.get(reverse('dashboard:shopkeeper'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['shop_count'], 1)
		self.assertEqual(response.context['active_shop_count'], 0)
		self.assertEqual(response.context['product_count'], 2)
		self.assertEqual(response.context['active_product_count'], 1)
		self.assertEqual(response.context['inactive_product_count'], 1)
		self.assertEqual(response.context['order_count'], 0)
		self.assertContains(response, 'Dashboard Shop')
		self.assertContains(response, 'Pending')
		self.assertNotContains(response, 'Private Other Shop')
		self.assertNotContains(response, 'Other owner item')


class RoleAccessTests(TestCase):
	password = 'BENI-test-password-2026!'

	def setUp(self):
		self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
		self.repair_worker_group, _ = Group.objects.get_or_create(name='Repair Worker')

	def create_user(self, username, group=None, is_staff=False):
		user = get_user_model().objects.create_user(
			username=username,
			password=self.password,
			is_staff=is_staff,
		)
		if group is not None:
			user.groups.add(group)
		return user

	def test_login_redirects_to_assigned_role_workspace(self):
		users = (
			('role-customer', None, False, 'dashboard:customer'),
			('role-shopkeeper', self.shopkeeper_group, False, 'dashboard:shopkeeper'),
			('role-repair-worker', self.repair_worker_group, False, 'dashboard:repair_worker'),
			('role-staff', None, True, 'dashboard:admin'),
		)
		for username, group, is_staff, route_name in users:
			with self.subTest(username=username):
				self.client.logout()
				self.create_user(username, group=group, is_staff=is_staff)
				response = self.client.post(
					reverse('accounts:login'),
					{'username': username, 'password': self.password},
				)
				self.assertRedirects(
					response,
					reverse(route_name),
					fetch_redirect_response=False,
				)

	def test_exact_shopkeeper_group_grants_only_shopkeeper_workspace(self):
		shopkeeper = self.create_user('exact-shopkeeper', group=self.shopkeeper_group)
		self.client.force_login(shopkeeper)

		self.assertEqual(
			self.client.get(reverse('dashboard:shopkeeper')).status_code,
			200,
		)
		self.assertEqual(
			self.client.get(reverse('dashboard:repair_worker')).status_code,
			403,
		)
		self.assertEqual(
			self.client.get(reverse('dashboard:admin')).status_code,
			302,
		)

		wrong_group, _ = Group.objects.get_or_create(name='Shopkeepers')
		wrong_user = self.create_user('wrong-shopkeeper', group=wrong_group)
		self.client.force_login(wrong_user)
		self.assertEqual(
			self.client.get(reverse('dashboard:shopkeeper')).status_code,
			403,
		)

	def test_exact_repair_worker_group_grants_only_repair_workspace(self):
		repair_worker = self.create_user(
			'exact-repair-worker',
			group=self.repair_worker_group,
		)
		self.client.force_login(repair_worker)

		self.assertEqual(
			self.client.get(reverse('dashboard:repair_worker')).status_code,
			200,
		)
		self.assertEqual(
			self.client.get(reverse('dashboard:shopkeeper')).status_code,
			403,
		)
		self.assertEqual(
			self.client.get(reverse('dashboard:admin')).status_code,
			302,
		)

		wrong_group, _ = Group.objects.get_or_create(name='Repair Workers')
		wrong_user = self.create_user('wrong-repair-worker', group=wrong_group)
		self.client.force_login(wrong_user)
		self.assertEqual(
			self.client.get(reverse('dashboard:repair_worker')).status_code,
			403,
		)

	def test_customer_and_nonstaff_users_cannot_open_other_workspaces(self):
		customer = self.create_user('direct-customer')
		self.client.force_login(customer)

		for route_name in ('dashboard:shopkeeper', 'dashboard:repair_worker'):
			with self.subTest(route=route_name):
				self.assertEqual(self.client.get(reverse(route_name)).status_code, 403)
		self.assertEqual(self.client.get(reverse('dashboard:admin')).status_code, 302)

		staff_user = self.create_user('staff-user', is_staff=True)
		self.client.force_login(staff_user)
		self.assertEqual(self.client.get(reverse('dashboard:admin')).status_code, 200)
		self.assertEqual(self.client.get(reverse('dashboard:customer')).status_code, 403)



class CaseVariantRoleAccessTests(TestCase):
	password = 'BENI-test-password-2026!'

	def test_case_variant_group_names_do_not_grant_role_access(self):
		lowercase_shopkeeper = Group.objects.create(name='shopkeeper')
		lowercase_repair_worker = Group.objects.create(name='repair worker')
		shop_user = get_user_model().objects.create_user(
			username='lowercase-shopkeeper',
			password=self.password,
		)
		repair_user = get_user_model().objects.create_user(
			username='lowercase-repair-worker',
			password=self.password,
		)
		shop_user.groups.add(lowercase_shopkeeper)
		repair_user.groups.add(lowercase_repair_worker)

		self.client.force_login(shop_user)
		self.assertEqual(self.client.get(reverse('dashboard:shopkeeper')).status_code, 403)
		self.client.logout()
		self.client.force_login(repair_user)
		self.assertEqual(self.client.get(reverse('dashboard:repair_worker')).status_code, 403)
