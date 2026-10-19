from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from products.models import Product
from shops.models import Shop
from verification.models import VerificationApplication

from .views import CART_OWNER_SESSION_KEY


class CustomerCartTests(TestCase):
    def setUp(self):
        self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
        self.customer = get_user_model().objects.create_user(username='customer-cart-user')
        self.shop_owner = get_user_model().objects.create_user(username='shop-cart-owner')
        self.shop_owner.groups.add(self.shopkeeper_group)
        Profile.objects.create(
            user=self.shop_owner,
            phone='+15550100003',
            phone_verified=True,
        )
        self.shop = Shop.objects.create(
            owner=self.shop_owner,
            name='North Market',
            category='Groceries',
            phone='555-0100',
            address='1 Main St',
            city='Sample City',
            state='Sample State',
            postal_code='12345',
            is_active=True,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name='Green Tea',
            category='Tea',
            price=Decimal('4.50'),
            stock_quantity=5,
            is_active=True,
        )
        self.verification = VerificationApplication.objects.create(
            applicant=self.shop_owner,
            shop=self.shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
            status=VerificationApplication.STATUS_APPROVED,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            aadhaar_status=VerificationApplication.CHECK_VERIFIED,
        )

    def make_shop_and_product(self, suffix, *, active=True, phone_status=None,
                              aadhaar_status=None, pan_status=None,
                              application_status=VerificationApplication.STATUS_APPROVED):
        owner = get_user_model().objects.create_user(username=f'owner-{suffix}')
        owner.groups.add(self.shopkeeper_group)
        Profile.objects.create(
            user=owner,
            phone='+15550100004',
            phone_verified=True,
        )
        shop = Shop.objects.create(
            owner=owner,
            name=f'Shop {suffix}',
            category='General',
            phone='555-0101',
            address='2 Main St',
            city='Sample City',
            state='Sample State',
            postal_code='12345',
            is_active=active,
        )
        verification_values = {
            'applicant': owner,
            'shop': shop,
            'application_type': VerificationApplication.TYPE_SHOPKEEPER,
            'status': application_status,
            'phone_status': phone_status or VerificationApplication.CHECK_VERIFIED,
            'aadhaar_status': (
                aadhaar_status or VerificationApplication.CHECK_VERIFIED
            ),
            'pan_status': pan_status or VerificationApplication.CHECK_NOT_SUBMITTED,
        }
        VerificationApplication.objects.create(**verification_values)
        product = Product.objects.create(
            shop=shop,
            name=f'Product {suffix}',
            category='General',
            price=Decimal('2.00'),
            stock_quantity=3,
            is_active=True,
        )
        return shop, product

    def test_customer_can_add_update_remove_cart_items(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('customers:cart_add', args=[self.product.pk]),
            {'quantity': 2},
        )
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)
        cart = self.client.session.get('beni_cart')
        self.assertEqual(cart[str(self.product.pk)]['quantity'], 2)

        response = self.client.post(
            reverse('customers:cart_update', args=[self.product.pk]),
            {'quantity': 3},
        )
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)
        cart = self.client.session.get('beni_cart')
        self.assertEqual(cart[str(self.product.pk)]['quantity'], 3)

        response = self.client.post(reverse('customers:cart_remove', args=[self.product.pk]))
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)
        self.assertNotIn(str(self.product.pk), self.client.session.get('beni_cart', {}))

    def test_cart_update_rejects_get_without_mutating_session(self):
        self.client.force_login(self.customer)
        cart = {
            str(self.product.pk): {
                'product_id': self.product.pk,
                'quantity': 1,
                'unit_price': str(self.product.price),
            }
        }
        session = self.client.session
        session['beni_cart'] = cart
        session.save()

        response = self.client.get(
            reverse('customers:cart_update', args=[self.product.pk]),
            {'quantity': 2},
        )

        self.assertEqual(response.status_code, 405)
        self.assertEqual(self.client.session['beni_cart'], cart)

    def test_cart_is_cleared_when_session_owner_does_not_match_customer(self):
        previous_owner = get_user_model().objects.create_user(
            username='previous-cart-owner',
        )
        self.client.force_login(self.customer)
        session = self.client.session
        session[CART_OWNER_SESSION_KEY] = str(previous_owner.pk)
        session['beni_cart'] = {
            str(self.product.pk): {
                'product_id': self.product.pk,
                'quantity': 1,
                'unit_price': str(self.product.price),
            }
        }
        session['beni_checkout_state'] = {
            'token': 'old-checkout-token',
            'cart_digest': 'old-cart-digest',
        }
        session['beni_checkout_receipts'] = {'old-token': 'old-digest'}
        session.save()

        response = self.client.get(reverse('customers:cart'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.product.name)
        session = self.client.session
        self.assertEqual(session['beni_cart'], {})
        self.assertEqual(session[CART_OWNER_SESSION_KEY], str(self.customer.pk))
        self.assertNotIn('beni_checkout_state', session)
        self.assertNotIn('beni_checkout_receipts', session)

    def test_catalog_excludes_products_without_current_market_eligibility(self):
        _, unverified_product = self.make_shop_and_product(
            'unverified',
            application_status=VerificationApplication.STATUS_REJECTED,
        )
        _, phone_pending_product = self.make_shop_and_product(
            'phone-pending',
            phone_status=VerificationApplication.CHECK_PENDING,
        )
        _, no_identity_check_product = self.make_shop_and_product(
            'no-id-check',
            aadhaar_status=VerificationApplication.CHECK_NOT_SUBMITTED,
            pan_status=VerificationApplication.CHECK_NOT_SUBMITTED,
        )
        _, inactive_product = self.make_shop_and_product(
            'inactive-shop',
            active=False,
        )
        _, inactive_listing = self.make_shop_and_product('inactive-product')
        inactive_listing.is_active = False
        inactive_listing.save(update_fields=('is_active',))

        response = self.client.get(reverse('catalog:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.name)
        for product in (
            unverified_product,
            phone_pending_product,
            no_identity_check_product,
            inactive_product,
            inactive_listing,
        ):
            self.assertNotContains(response, product.name)

    def test_changing_verified_owner_mobile_removes_products_from_public_catalog(self):
        self.assertContains(
            self.client.get(reverse('catalog:list')),
            self.product.name,
        )

        profile = self.shop_owner.profile
        profile.phone = '+15550100010'
        profile.save()

        response = self.client.get(reverse('catalog:list'))
        self.shop.refresh_from_db()
        self.verification.refresh_from_db()
        self.assertNotContains(response, self.product.name)
        self.assertFalse(self.shop.is_active)
        self.assertEqual(
            self.verification.status,
            VerificationApplication.STATUS_PENDING,
        )

    def test_cart_rejects_and_removes_product_when_shop_becomes_ineligible(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('customers:cart_add', args=[self.product.pk]),
            {'quantity': 1},
        )
        self.assertRedirects(
            response,
            reverse('customers:cart'),
            fetch_redirect_response=False,
        )
        self.client.get(reverse('customers:cart'))

        self.verification.status = VerificationApplication.STATUS_REJECTED
        self.verification.save(update_fields=('status',))
        session = self.client.session
        session['beni_cart'] = {
            str(self.product.pk): {
                'product_id': self.product.pk,
                'quantity': 1,
                'unit_price': str(self.product.price),
            }
        }
        session[CART_OWNER_SESSION_KEY] = str(self.customer.pk)
        session.save()

        response = self.client.get(reverse('customers:cart'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.product.name)
        self.assertEqual(self.client.session['beni_cart'], {})

    def test_cart_rejects_invalid_stock_and_price_tampering(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('customers:cart_add', args=[self.product.pk]),
            {'quantity': 99},
        )
        self.assertRedirects(
            response,
            reverse('catalog:detail', args=[self.product.pk]),
            fetch_redirect_response=False,
        )
        self.assertNotIn(str(self.product.pk), self.client.session.get('beni_cart', {}))

        self.client.session['beni_cart'] = {
            str(self.product.pk): {
                'product_id': self.product.pk,
                'shop_id': self.shop.pk,
                'shop_name': self.shop.name,
                'name': self.product.name,
                'category': self.product.category,
                'quantity': 1,
                'unit_price': '99.99',
                'image': '',
            }
        }
        self.client.session[CART_OWNER_SESSION_KEY] = str(self.customer.pk)
        self.client.session.save()
        response = self.client.get(reverse('customers:checkout'))
        self.assertRedirects(response, reverse('customers:cart'), fetch_redirect_response=False)

    def test_non_customer_accounts_cannot_manage_cart_or_checkout(self):
        shopkeeper = get_user_model().objects.create_user(username='shopkeeper-cart-user')
        shopkeeper.groups.add(self.shopkeeper_group)
        self.client.force_login(shopkeeper)
        self.assertEqual(self.client.get(reverse('customers:cart')).status_code, 403)
        self.assertEqual(self.client.get(reverse('customers:checkout')).status_code, 403)

        administrator = get_user_model().objects.create_user(
            username='staff-cart-user',
            is_staff=True,
        )
        self.client.force_login(administrator)
        self.assertEqual(self.client.get(reverse('customers:cart')).status_code, 403)
        self.assertEqual(self.client.get(reverse('customers:checkout')).status_code, 403)
