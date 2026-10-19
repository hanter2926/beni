from django.test import SimpleTestCase
from django.urls import resolve, reverse

from customers.views import cart_view
from dashboard.views import customer_dashboard
from orders.views import order_history


class CustomerFacadeTests(SimpleTestCase):
    def test_facade_urls_reuse_canonical_customer_views(self):
        cases = (
            ('Customer:dashboard', (), customer_dashboard),
            ('Customer:cart', (), cart_view),
            ('Customer:orders', (), order_history),
        )
        for name, args, canonical_view in cases:
            with self.subTest(name=name):
                match = resolve(reverse(name, args=args))
                self.assertIs(match.func, canonical_view)
