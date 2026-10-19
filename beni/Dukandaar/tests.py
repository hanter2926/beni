from django.test import SimpleTestCase
from django.urls import resolve, reverse

from dashboard.views import shopkeeper_dashboard
from orders.views import shopkeeper_order_list
from products.views import product_list
from shops.views import shop_list
from verification.views import shopkeeper_application


class DukandaarFacadeTests(SimpleTestCase):
    def test_facade_urls_reuse_canonical_shopkeeper_views(self):
        cases = (
            ('Dukandaar:dashboard', (), shopkeeper_dashboard),
            ('Dukandaar:shops', (), shop_list),
            ('Dukandaar:products', (), product_list),
            ('Dukandaar:orders', (), shopkeeper_order_list),
            ('Dukandaar:shop_verification', (1,), shopkeeper_application),
        )
        for name, args, canonical_view in cases:
            with self.subTest(name=name):
                match = resolve(reverse(name, args=args))
                self.assertIs(match.func, canonical_view)
