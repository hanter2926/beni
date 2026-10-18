from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.http import Http404
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from types import SimpleNamespace
from unittest.mock import patch

from notifications.models import Notification
from verification.models import VerificationApplication

from .models import BookingAssignmentEvent, RepairBooking
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


class BookingNotificationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.worker_group, _ = Group.objects.get_or_create(
            name='Repair Worker',
        )
        self.customer = user_model.objects.create_user(
            username='booking-notification-customer',
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
