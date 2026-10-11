from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse
from django.test.client import RequestFactory


class DashboardRouteTests(SimpleTestCase):
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
			is_authenticated=True,
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
