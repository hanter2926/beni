from django.test import SimpleTestCase
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
