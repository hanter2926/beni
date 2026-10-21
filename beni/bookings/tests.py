from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import Http404
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from types import SimpleNamespace
from unittest.mock import patch

from notifications.models import Notification
from accounts.models import Profile
from verification.models import VerificationApplication

from .categories import REPAIR_CATEGORY_CHOICES
from .forms import RepairBookingForm
from .models import BookingAssignmentEvent, BookingSupportRequest, RepairBooking
from .services import assign_worker, transition_worker_booking


class PrivateBookingImageAccessTests(SimpleTestCase):
    def make_request(self, user_id, is_staff=False):
        request = RequestFactory().get('/repairs/images/14/')
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            is_staff=is_staff,
            pk=user_id,
        )
        return request

    @patch('bookings.views.private_image_response', return_value=HttpResponse('image'))
    @patch('bookings.views.get_object_or_404')
    def test_customer_can_access_own_booking_image(self, get_image, make_response):
        image_record = SimpleNamespace(
            booking=SimpleNamespace(customer_id=3, assigned_worker_id=5),
            image=object(),
        )
        get_image.return_value = image_record

        from bookings.views import private_booking_image

        response = private_booking_image(self.make_request(3), 14)

        self.assertEqual(response.status_code, 200)
        make_response.assert_called_once_with(image_record.image)

    @patch('bookings.views.private_image_response', return_value=HttpResponse('image'))
    @patch('bookings.views.get_object_or_404')
    def test_assigned_worker_can_access_booking_image(self, get_image, make_response):
        image_record = SimpleNamespace(
            booking=SimpleNamespace(customer_id=3, assigned_worker_id=5),
            image=object(),
        )
        get_image.return_value = image_record

        from bookings.views import private_booking_image

        response = private_booking_image(self.make_request(5), 14)

        self.assertEqual(response.status_code, 200)
        make_response.assert_called_once_with(image_record.image)

    @patch('bookings.views.get_object_or_404')
    def test_unrelated_user_cannot_access_booking_image(self, get_image):
        get_image.return_value = SimpleNamespace(
            booking=SimpleNamespace(customer_id=3, assigned_worker_id=5),
            image=object(),
        )

        from bookings.views import private_booking_image

        with self.assertRaises(Http404):
            private_booking_image(self.make_request(9), 14)


class RepairCategoryFormTests(SimpleTestCase):
    def test_booking_form_uses_the_customer_dashboard_categories(self):
        form = RepairBookingForm()

        self.assertEqual(
            tuple(form.fields['service_category'].choices[1:]),
            REPAIR_CATEGORY_CHOICES,
        )
        self.assertIn(
            ('Other repairs', 'Other repairs'),
            form.fields['service_category'].choices,
        )


class BookingNotificationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.worker_group, _ = Group.objects.get_or_create(
            name='Repair Worker',
        )
        self.customer = user_model.objects.create_user(
            username='booking-notification-customer',
        )
        Profile.objects.create(
            user=self.customer,
            phone='+15550100002',
            phone_verified=True,
        )
        self.staff = user_model.objects.create_user(
            username='booking-notification-staff',
            is_staff=True,
        )
        self.worker = self.make_worker('one')
        self.replacement_worker = self.make_worker('two')
        self.booking = RepairBooking.objects.create(
            customer=self.customer,
            service_category='Plumbing',
            problem_description='Leaking tap',
            service_address='Private address not used in notification.',
            preferred_at='2030-01-01T12:00:00Z',
        )

    def make_worker(self, suffix):
        worker = get_user_model().objects.create_user(
            username=f'booking-notification-worker-{suffix}',
        )
        worker.groups.add(self.worker_group)
        Profile.objects.create(
            user=worker,
            phone='+15550100000',
            phone_verified=True,
        )
        VerificationApplication.objects.create(
            applicant=worker,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
            status=VerificationApplication.STATUS_APPROVED,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            face_status=VerificationApplication.CHECK_VERIFIED,
        )
        return worker

    def test_assignment_history_distinguishes_later_reassignment(self):
        assign_worker(
            booking_id=self.booking.pk,
            worker=self.worker,
            actor=self.staff,
        )
        first_assignment = BookingAssignmentEvent.objects.get()
        transition_worker_booking(
            booking_id=self.booking.pk,
            worker=self.worker,
            new_status=RepairBooking.STATUS_REJECTED,
        )
        assign_worker(
            booking_id=self.booking.pk,
            worker=self.replacement_worker,
            actor=self.staff,
        )

        assignments = list(
            BookingAssignmentEvent.objects.filter(booking=self.booking)
        )
        self.assertEqual(len(assignments), 2)
        self.assertEqual(assignments[0].assigned_worker, self.worker)
        self.assertEqual(assignments[1].assigned_worker, self.replacement_worker)
        self.assertEqual(assignments[1].previous_worker, self.worker)
        self.assertNotEqual(assignments[0].pk, assignments[1].pk)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.worker,
                event_key=f'booking-assignment:{first_assignment.pk}:worker',
            ).exists()
        )
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.customer,
                title='Repair worker assigned',
            ).count(),
            2,
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.worker,
                title='Repair job reassigned',
            ).exists()
        )

    def test_assignment_and_notification_roll_back_together(self):
        from unittest.mock import patch

        with patch(
            'bookings.services.create_notification',
            side_effect=RuntimeError('notification persistence failed'),
        ):
            with self.assertRaises(RuntimeError):
                assign_worker(
                    booking_id=self.booking.pk,
                    worker=self.worker,
                    actor=self.staff,
                )

        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, RepairBooking.STATUS_REQUESTED)
        self.assertIsNone(self.booking.assigned_worker_id)
        self.assertFalse(
            BookingAssignmentEvent.objects.filter(booking=self.booking).exists()
        )

    def test_contact_is_visible_only_to_booking_participants(self):
        assign_worker(
            booking_id=self.booking.pk,
            worker=self.worker,
            actor=self.staff,
        )
        self.client.force_login(self.customer)
        customer_response = self.client.get(
            f'/repairs/{self.booking.pk}/',
        )
        self.assertEqual(customer_response.status_code, 200)
        self.assertContains(customer_response, '+15550100000')
        self.assertContains(customer_response, 'https://wa.me/15550100000')

        self.client.force_login(self.worker)
        worker_response = self.client.get('/repairs/worker/')
        self.assertEqual(worker_response.status_code, 200)
        self.assertContains(worker_response, '+15550100002')

        self.client.force_login(self.replacement_worker)
        unrelated_worker_response = self.client.get('/repairs/worker/')
        self.assertEqual(unrelated_worker_response.status_code, 200)
        self.assertNotContains(unrelated_worker_response, '+15550100002')
        self.assertNotContains(
            unrelated_worker_response,
            self.booking.service_address,
        )

        other_customer = get_user_model().objects.create_user(
            username='booking-unrelated-customer',
        )
        self.client.force_login(other_customer)
        self.assertEqual(
            self.client.get(f'/repairs/{self.booking.pk}/').status_code,
            404,
        )

    def test_worker_service_address_is_hidden_after_booking_ends(self):
        assign_worker(
            booking_id=self.booking.pk,
            worker=self.worker,
            actor=self.staff,
        )
        self.client.force_login(self.worker)

        active_response = self.client.get('/repairs/worker/')
        self.assertContains(active_response, self.booking.service_address)

        for status in (
            RepairBooking.STATUS_COMPLETED,
            RepairBooking.STATUS_CANCELLED,
            RepairBooking.STATUS_DISPUTED,
        ):
            with self.subTest(status=status):
                self.booking.status = status
                self.booking.save(update_fields=('status',))

                response = self.client.get('/repairs/worker/')

                self.assertNotContains(response, self.booking.service_address)
                self.assertContains(
                    response,
                    'The service address is no longer available for this job.',
                )

    def test_safety_support_is_staff_scoped_and_disputes_active_booking(self):
        assign_worker(
            booking_id=self.booking.pk,
            worker=self.worker,
            actor=self.staff,
        )
        self.client.force_login(self.customer)
        response = self.client.post(
            f'/repairs/{self.booking.pk}/support/',
            {
                'request_type': BookingSupportRequest.TYPE_SAFETY,
                'description': 'Please have a staff member contact me.',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, RepairBooking.STATUS_DISPUTED)
        self.assertTrue(
            BookingSupportRequest.objects.filter(
                booking=self.booking,
                reporter=self.customer,
                request_type=BookingSupportRequest.TYPE_SAFETY,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.staff,
                title='Repair booking support requested',
            ).exists()
        )
        self.assertNotContains(
            self.client.get(f'/repairs/{self.booking.pk}/'),
            '+15550100000',
        )

        self.client.force_login(self.replacement_worker)
        self.assertEqual(
            self.client.post(
                f'/repairs/{self.booking.pk}/support/',
                {
                    'request_type': BookingSupportRequest.TYPE_COMPLAINT,
                    'description': 'Not my booking.',
                },
            ).status_code,
            404,
        )
