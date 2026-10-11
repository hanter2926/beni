from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command, CommandError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse


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
