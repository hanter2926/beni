from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.http import Http404, HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse

from .context_processors import navigation_context
from .views import private_profile_image


class PrivateProfileImageAccessTests(SimpleTestCase):
	def make_request(self, user_id, is_staff=False):
		request = RequestFactory().get(f'/accounts/profiles/{user_id}/image/')
		request.user = SimpleNamespace(
			is_authenticated=True,
			is_active=True,
			is_staff=is_staff,
			pk=user_id,
		)
		return request

	@patch('accounts.views.private_image_response', return_value=HttpResponse('image'))
	@patch('accounts.views.get_object_or_404')
	def test_owner_can_access_private_profile_image(self, get_profile, make_response):
		profile = SimpleNamespace(image=object())
		get_profile.return_value = profile

		response = private_profile_image(self.make_request(7), 7)

		self.assertEqual(response.status_code, 200)
		make_response.assert_called_once_with(profile.image)

	@patch('accounts.views.get_object_or_404')
	def test_other_non_staff_user_cannot_access_profile_image(self, get_profile):
		with self.assertRaises(Http404):
			private_profile_image(self.make_request(8), 7)
		get_profile.assert_not_called()

	@patch('accounts.views.private_image_response', return_value=HttpResponse('image'))
	@patch('accounts.views.get_object_or_404')
	def test_staff_can_access_another_users_profile_image(self, get_profile, make_response):
		profile = SimpleNamespace(image=object())
		get_profile.return_value = profile

		response = private_profile_image(self.make_request(8, is_staff=True), 7)

		self.assertEqual(response.status_code, 200)
		make_response.assert_called_once_with(profile.image)


class NavigationContextTests(SimpleTestCase):
	def make_request(self, user, session=None):
		return SimpleNamespace(user=user, session=session or {})

	def make_customer(self, user_id=7):
		groups = SimpleNamespace(values_list=lambda *args, **kwargs: ())
		return SimpleNamespace(
			is_authenticated=True,
			is_staff=False,
			pk=user_id,
			groups=groups,
		)

	def test_customer_cart_count_uses_owned_session_items_only(self):
		request = self.make_request(
			self.make_customer(),
			{
				'beni_cart_owner_id': '7',
				'beni_cart': {
					'1': {'quantity': 2},
					'2': {'quantity': 3},
					'3': {'quantity': 'invalid'},
					'4': {'quantity': True},
				},
			},
		)

		context = navigation_context(request)

		self.assertEqual(context['role_label'], 'Customer')
		self.assertEqual(context['cart_item_count'], 5)

	def test_cart_count_is_not_exposed_for_another_session_owner(self):
		request = self.make_request(
			self.make_customer(),
			{
				'beni_cart_owner_id': '8',
				'beni_cart': {'1': {'quantity': 4}},
			},
		)

		self.assertEqual(navigation_context(request)['cart_item_count'], 0)

	def test_navigation_context_provides_admin_breadcrumb(self):
		request = RequestFactory().get(reverse('dashboard:admin_users'))
		request.user = SimpleNamespace(
			is_authenticated=True,
			is_staff=True,
			pk=9,
		)
		request.resolver_match = resolve(request.path)

		context = navigation_context(request)

		self.assertEqual(context['role_label'], 'Admin')
		self.assertEqual(context['workspace_url'], reverse('dashboard:admin'))
		self.assertEqual(context['current_page_label'], 'Marketplace users')


class AuthenticationPageTests(SimpleTestCase):
	def test_login_and_registration_pages_render(self):
		for route_name, template_name in (
			('accounts:login', 'auth/login.html'),
			('accounts:register', 'auth/register.html'),
		):
			with self.subTest(route=route_name):
				response = self.client.get(reverse(route_name))
				self.assertEqual(response.status_code, 200)
				self.assertTemplateUsed(response, template_name)


class AuthenticationFlowTests(TestCase):
	password = 'BENI-test-password-2026!'

	def create_user(self, username, **extra_fields):
		return get_user_model().objects.create_user(
			username=username,
			password=self.password,
			**extra_fields,
		)

	def test_registration_creates_default_customer_without_privileges(self):
		response = self.client.post(
			reverse('accounts:register'),
			{
				'username': 'new-customer',
				'password1': self.password,
				'password2': self.password,
			},
		)

		self.assertRedirects(
			response,
			reverse('dashboard:customer'),
			fetch_redirect_response=False,
		)
		user = get_user_model().objects.get(username='new-customer')
		self.assertIsInstance(user, get_user_model())
		self.assertFalse(user.is_staff)
		self.assertFalse(user.is_superuser)
		self.assertFalse(user.groups.exists())
		self.assertEqual(
			self.client.get(reverse('dashboard:customer')).status_code,
			200,
		)

	def test_successful_customer_login_uses_safe_role_redirect(self):
		self.create_user('customer-login')

		response = self.client.post(
			reverse('accounts:login'),
			{
				'username': 'customer-login',
				'password': self.password,
				'next': 'https://outside.example/steal-session',
			},
		)

		self.assertRedirects(
			response,
			reverse('dashboard:customer'),
			fetch_redirect_response=False,
		)

	def test_logout_is_post_only_and_ends_session(self):
		user = self.create_user('logout-user')
		self.client.force_login(user)

		self.assertEqual(self.client.get(reverse('accounts:logout')).status_code, 405)
		response = self.client.post(reverse('accounts:logout'))
		self.assertRedirects(
			response,
			reverse('accounts:login'),
			fetch_redirect_response=False,
		)
		self.assertEqual(
			self.client.get(reverse('dashboard:customer')).status_code,
			302,
		)

	def test_authentication_post_routes_enforce_csrf(self):
		csrf_client = Client(enforce_csrf_checks=True)
		user = self.create_user('csrf-user')
		csrf_client.force_login(user)

		login_response = csrf_client.post(
			reverse('accounts:login'),
			{'username': 'csrf-user', 'password': self.password},
		)
		registration_response = csrf_client.post(
			reverse('accounts:register'),
			{
				'username': 'csrf-registration',
				'password1': self.password,
				'password2': self.password,
			},
		)
		logout_response = csrf_client.post(reverse('accounts:logout'))

		self.assertEqual(login_response.status_code, 403)
		self.assertEqual(registration_response.status_code, 403)
		self.assertEqual(logout_response.status_code, 403)
		self.assertFalse(
			get_user_model().objects.filter(username='csrf-registration').exists()
		)

	def test_role_group_command_is_repeatable(self):
		call_command('create_role_groups', stdout=StringIO())
		call_command('create_role_groups', stdout=StringIO())

		group_names = set(
			Group.objects.filter(
				name__in=('Shopkeeper', 'Repair Worker')
			).values_list('name', flat=True)
		)
		self.assertEqual(group_names, {'Shopkeeper', 'Repair Worker'})

	def test_role_group_command_refuses_case_colliding_groups(self):
		Group.objects.create(name='shopkeeper')

		with self.assertRaises(CommandError):
			call_command('create_role_groups', stdout=StringIO())

		self.assertEqual(
			set(Group.objects.values_list('name', flat=True)),
			{'shopkeeper'},
		)
