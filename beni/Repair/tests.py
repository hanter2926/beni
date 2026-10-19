from django.test import SimpleTestCase
from django.urls import resolve, reverse

from bookings.views import (
    customer_booking_create,
    customer_booking_list,
    worker_booking_list,
)


class RepairFacadeTests(SimpleTestCase):
    def test_facade_urls_reuse_canonical_booking_views(self):
        cases = (
            ('Repair:customer_list', (), customer_booking_list),
            ('Repair:customer_create', (), customer_booking_create),
            ('Repair:worker_list', (), worker_booking_list),
        )
        for name, args, canonical_view in cases:
            with self.subTest(name=name):
                match = resolve(reverse(name, args=args))
                self.assertIs(match.func, canonical_view)
