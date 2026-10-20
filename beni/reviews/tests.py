from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from bookings.models import RepairBooking
from accounts.models import Profile
from orders.models import CheckoutAttempt, Order
from products.models import Product
from shops.models import Shop
from verification.models import VerificationApplication

from .forms import ReviewModerationForm
from .models import Review
from .services import (
    ReviewWorkflowError,
    moderate_review,
    submit_order_review,
    submit_repair_review,
)


class ReviewWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(
            username='review-customer',
            password='test-password',
        )
        self.other_customer = user_model.objects.create_user(
            username='review-other',
            password='test-password',
        )
        self.owner = user_model.objects.create_user(
            username='review-shopkeeper',
            password='test-password',
        )
        shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
        self.owner.groups.add(shopkeeper_group)
        self.worker = user_model.objects.create_user(
            username='review-worker',
            password='test-password',
        )
        worker_group, _ = Group.objects.get_or_create(name='Repair Worker')
        self.worker.groups.add(worker_group)
        Profile.objects.create(
            user=self.worker,
            phone='+15550100013',
            phone_verified=True,
        )
        VerificationApplication.objects.create(
            applicant=self.worker,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
            status=VerificationApplication.STATUS_APPROVED,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            face_status=VerificationApplication.CHECK_VERIFIED,
        )
        self.staff = user_model.objects.create_user(
            username='review-staff',
            password='test-password',
            is_staff=True,
        )
        self.shop = Shop.objects.create(
            owner=self.owner,
            name='Review Shop',
            category='General',
            phone='555-0100',
            address='1 Main Street',
            city='Test City',
            state='Test State',
            postal_code='12345',
        )
        Profile.objects.create(
            user=self.owner,
            phone='+15550100014',
            phone_verified=True,
        )
        VerificationApplication.objects.create(
            applicant=self.owner,
            shop=self.shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
            status=VerificationApplication.STATUS_APPROVED,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            aadhaar_status=VerificationApplication.CHECK_VERIFIED,
        )
        self.product = Product.objects.create(
            shop=self.shop,
            name='Review Product',
            category='General',
            price=Decimal('10.00'),
            stock_quantity=3,
        )
        self.checkout = CheckoutAttempt.objects.create(
            customer=self.customer,
            token='71703eac-2b26-4bfc-a6ab-10858feef00a',
            cart_digest='b' * 64,
        )
        self.order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            checkout_attempt=self.checkout,
            order_number='BENI-REVIEW-1',
            status=Order.STATUS_DELIVERED,
            payment_status=Order.PAYMENT_PAID,
            contact_name='Review Customer',
            contact_phone='555-0101',
            address_line1='2 Market Road',
            city='Test City',
            state='Test State',
            postal_code='12345',
            subtotal=Decimal('10.00'),
            total=Decimal('10.00'),
        )
        self.booking = RepairBooking.objects.create(
            customer=self.customer,
            assigned_worker=self.worker,
            service_category='Mobile repair',
            problem_description='A completed repair',
            service_address='3 Service Road',
            preferred_at='2030-01-01T12:00:00Z',
            status=RepairBooking.STATUS_COMPLETED,
        )

    def test_only_customer_with_delivered_order_can_submit_one_order_review(self):
        review = submit_order_review(
            order_number=self.order.order_number,
            customer=self.customer,
            rating=5,
            body='Helpful local shop.',
        )

        self.assertEqual(review.status, Review.STATUS_PENDING)
        self.assertEqual(review.order, self.order)
        with self.assertRaisesMessage(
            ReviewWorkflowError,
            'already reviewed',
        ):
            submit_order_review(
                order_number=self.order.order_number,
                customer=self.customer,
                rating=4,
                body='Duplicate',
            )
        self.assertIsNone(
            submit_order_review(
                order_number=self.order.order_number,
                customer=self.other_customer,
                rating=4,
                body='Not the buyer',
            )
        )

    def test_order_review_is_not_allowed_before_delivery(self):
        self.order.status = Order.STATUS_PROCESSING
        self.order.save(update_fields=('status',))

        with self.assertRaisesMessage(
            ReviewWorkflowError,
            'only after delivery',
        ):
            submit_order_review(
                order_number=self.order.order_number,
                customer=self.customer,
                rating=5,
                body='Too early',
            )

    def test_only_customer_with_completed_repair_can_submit_review(self):
        review = submit_repair_review(
            booking_id=self.booking.pk,
            customer=self.customer,
            rating=4,
            body='Repair completed.',
        )

        self.assertEqual(review.booking, self.booking)
        self.assertEqual(review.status, Review.STATUS_PENDING)
        self.assertIsNone(
            submit_repair_review(
                booking_id=self.booking.pk,
                customer=self.other_customer,
                rating=4,
                body='Not the customer',
            )
        )

    def test_review_must_reference_exactly_one_target_owned_by_customer(self):
        invalid_review = Review(
            customer=self.customer,
            rating=3,
        )
        with self.assertRaises(ValidationError):
            invalid_review.full_clean()

        wrong_owner_review = Review(
            customer=self.other_customer,
            order=self.order,
            rating=3,
        )
        with self.assertRaises(ValidationError):
            wrong_owner_review.full_clean()

    def test_staff_moderation_publishes_review_and_notifies_customer(self):
        review = submit_order_review(
            order_number=self.order.order_number,
            customer=self.customer,
            rating=5,
            body='Good service.',
        )

        changed = moderate_review(
            review_id=review.pk,
            moderator=self.staff,
            status=Review.STATUS_PUBLISHED,
        )

        self.assertEqual(changed.status, Review.STATUS_PUBLISHED)
        self.assertEqual(changed.moderator, self.staff)

    def test_rejected_review_requires_moderation_note(self):
        review = submit_order_review(
            order_number=self.order.order_number,
            customer=self.customer,
            rating=2,
            body='Review needing moderation.',
        )

        with self.assertRaisesMessage(
            ReviewWorkflowError,
            'Add a reason',
        ):
            moderate_review(
                review_id=review.pk,
                moderator=self.staff,
                status=Review.STATUS_REJECTED,
            )
        form = ReviewModerationForm(
            {'status': Review.STATUS_REJECTED, 'moderation_note': ''}
        )
        self.assertFalse(form.is_valid())

    def test_review_submission_page_requires_own_completed_order(self):
        self.client.force_login(self.customer)
        url = reverse(
            'reviews:submit_order',
            args=(self.order.order_number,),
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Review Review Shop')

        self.client.force_login(self.other_customer)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_invalid_order_review_preserves_input_and_shows_field_errors(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse(
                'reviews:submit_order',
                args=(self.order.order_number,),
            ),
            {'rating': 'invalid', 'body': 'Keep this review text.'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['form'].errors.keys(),
            {'rating'},
        )
        self.assertEqual(
            response.context['form']['body'].value(),
            'Keep this review text.',
        )
        self.assertContains(response, 'Choose a rating and correct the review text.')

    def test_invalid_repair_review_preserves_input_and_shows_field_errors(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('reviews:submit_repair', args=(self.booking.pk,)),
            {'rating': 'invalid', 'body': 'Keep this repair review.'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['form'].errors.keys(),
            {'rating'},
        )
        self.assertEqual(
            response.context['form']['body'].value(),
            'Keep this repair review.',
        )
        self.assertContains(response, 'Choose a rating and correct the review text.')

    def test_only_published_shop_reviews_are_visible_to_shopkeeper_and_catalog(self):
        review = submit_order_review(
            order_number=self.order.order_number,
            customer=self.customer,
            rating=5,
            body='A helpful published review.',
        )
        moderate_review(
            review_id=review.pk,
            moderator=self.staff,
            status=Review.STATUS_PUBLISHED,
        )

        self.client.force_login(self.owner)
        response = self.client.get(reverse('reviews:shopkeeper_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A helpful published review.')
        self.assertContains(response, '5.0 / 5')

        response = self.client.get(
            reverse('catalog:detail', args=(self.product.pk,))
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A helpful published review.')

    def test_verified_repair_worker_can_view_published_repair_review(self):
        review = submit_repair_review(
            booking_id=self.booking.pk,
            customer=self.customer,
            rating=4,
            body='A helpful repair review.',
        )
        moderate_review(
            review_id=review.pk,
            moderator=self.staff,
            status=Review.STATUS_PUBLISHED,
        )

        self.client.force_login(self.worker)
        response = self.client.get(reverse('reviews:worker_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'A helpful repair review.')

    def test_non_staff_cannot_open_review_moderation_queue(self):
        self.client.force_login(self.owner)

        response = self.client.get(reverse('reviews:moderation_queue'))

        self.assertEqual(response.status_code, 302)
