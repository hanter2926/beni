from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from notifications.models import Notification

from .models import VerificationApplication
from .services import review_application


class VerificationNotificationTests(TestCase):
    def setUp(self):
        self.worker_group, _ = Group.objects.get_or_create(name='Repair Worker')
        self.worker = get_user_model().objects.create_user(
            username='verification-notification-worker',
        )
        self.worker.groups.add(self.worker_group)
        self.staff = get_user_model().objects.create_user(
            username='verification-notification-admin',
            is_staff=True,
        )

    def test_new_application_notifies_staff_and_decision_notifies_applicant(self):
        self.client.force_login(self.worker)
        response = self.client.get(reverse('verification:worker_application'))

        self.assertEqual(response.status_code, 200)
        application = VerificationApplication.objects.get(applicant=self.worker)
        staff_notification = Notification.objects.get(
            recipient=self.staff,
            event_key=(
                f'verification-application:{application.pk}:created:admin'
            ),
        )
        self.assertEqual(
            staff_notification.destination_url,
            reverse('verification:admin_list'),
        )

        decision = review_application(
            application_id=application.pk,
            reviewer=self.staff,
            cleaned_data={
                'status': VerificationApplication.STATUS_APPROVED,
                'phone_status': VerificationApplication.CHECK_VERIFIED,
                'face_status': VerificationApplication.CHECK_VERIFIED,
                'reason': 'Requirements reviewed.',
            },
        )

        applicant_notification = Notification.objects.get(
            recipient=self.worker,
            event_key=f'verification-decision:{decision.pk}:applicant',
        )
        self.assertEqual(
            applicant_notification.destination_url,
            reverse('verification:worker_application'),
        )
        self.assertNotIn('Requirements reviewed.', applicant_notification.message)
