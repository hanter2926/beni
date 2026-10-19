from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from types import SimpleNamespace

from notifications.models import Notification
from accounts.models import Profile
from shops.models import Shop

from .models import VerificationApplication
from .services import review_application, submit_application


class PrivateVerificationDocumentAccessTests(SimpleTestCase):
    def make_request(self, is_staff):
        request = RequestFactory().get('/verification/admin/documents/2/')
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            is_staff=is_staff,
        )
        return request

    @patch('verification.views.private_document_response', return_value=HttpResponse('file'))
    @patch('verification.views.get_object_or_404')
    def test_staff_can_download_private_verification_document(
        self,
        get_document,
        make_response,
    ):
        document = SimpleNamespace(file=object())
        get_document.return_value = document

        from verification.views import admin_document

        response = admin_document(self.make_request(True), 2)

        self.assertEqual(response.status_code, 200)
        make_response.assert_called_once_with(document.file)

    def test_non_staff_cannot_download_verification_document(self):
        from verification.views import admin_document

        response = admin_document(self.make_request(False), 2)

        self.assertEqual(response.status_code, 302)


class VerificationNotificationTests(TestCase):
    def setUp(self):
        self.worker_group, _ = Group.objects.get_or_create(name='Repair Worker')
        self.shopkeeper_group, _ = Group.objects.get_or_create(name='Shopkeeper')
        self.worker = get_user_model().objects.create_user(
            username='verification-notification-worker',
        )
        self.worker.groups.add(self.worker_group)
        Profile.objects.create(
            user=self.worker,
            phone='+15550100001',
        )
        self.shopkeeper = get_user_model().objects.create_user(
            username='verification-notification-shopkeeper',
        )
        self.shopkeeper.groups.add(self.shopkeeper_group)
        Profile.objects.create(
            user=self.shopkeeper,
            phone='+15550100009',
        )
        self.shop = Shop.objects.create(
            owner=self.shopkeeper,
            name='Verification Test Shop',
            category='Grocery',
            phone='555-0100',
            address='10 Main Street',
            city='Example City',
            state='Example State',
            postal_code='12345',
            is_active=False,
        )
        self.staff = get_user_model().objects.create_user(
            username='verification-notification-admin',
            is_staff=True,
        )

    def test_get_does_not_create_applications_or_submission_notifications(self):
        self.client.force_login(self.worker)
        response = self.client.get(reverse('verification:worker_application'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Not submitted')
        self.assertFalse(
            VerificationApplication.objects.filter(applicant=self.worker).exists()
        )
        self.assertFalse(Notification.objects.exists())

        self.client.force_login(self.shopkeeper)
        response = self.client.get(
            reverse(
                'verification:shopkeeper_application',
                args=[self.shop.pk],
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Not submitted')
        self.assertFalse(
            VerificationApplication.objects.filter(shop=self.shop).exists()
        )
        self.assertFalse(Notification.objects.exists())

    def test_get_does_not_modify_an_existing_application(self):
        application = VerificationApplication.objects.create(
            applicant=self.worker,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
            status=VerificationApplication.STATUS_REJECTED,
            phone_status=VerificationApplication.CHECK_REJECTED,
            face_status=VerificationApplication.CHECK_REJECTED,
            decision_reason='Review required.',
            reviewed_by=self.staff,
        )
        updated_at = application.updated_at
        self.client.force_login(self.worker)

        response = self.client.get(reverse('verification:worker_application'))

        self.assertEqual(response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, VerificationApplication.STATUS_REJECTED)
        self.assertEqual(application.decision_reason, 'Review required.')
        self.assertEqual(application.updated_at, updated_at)
        self.assertFalse(Notification.objects.exists())

    def test_valid_worker_post_submits_once_and_notifies_staff_once(self):
        self.client.force_login(self.worker)
        url = reverse('verification:worker_application')

        first_response = self.client.post(url, {'confirmation': 'on'})
        second_response = self.client.post(url, {'confirmation': 'on'})

        self.assertRedirects(first_response, url, fetch_redirect_response=False)
        self.assertRedirects(second_response, url, fetch_redirect_response=False)
        application = VerificationApplication.objects.get(applicant=self.worker)
        self.assertEqual(application.status, VerificationApplication.STATUS_PENDING)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.staff,
                event_key=f'verification-application:{application.pk}:created:admin',
            ).count(),
            1,
        )
        self.assertEqual(
            Notification.objects.get(
                recipient=self.staff,
                event_key=f'verification-application:{application.pk}:created:admin',
            ).destination_url,
            reverse('verification:admin_list'),
        )

    def test_invalid_post_preserves_form_errors_without_creating_records(self):
        self.client.force_login(self.worker)

        response = self.client.post(
            reverse('verification:worker_application'),
            {},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This field is required.')
        self.assertTrue(response.context['form'].is_bound)
        self.assertFalse(
            VerificationApplication.objects.filter(applicant=self.worker).exists()
        )
        self.assertFalse(Notification.objects.exists())

    def test_rejected_application_resubmission_notifies_only_once(self):
        application = VerificationApplication.objects.create(
            applicant=self.worker,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
        )
        review_application(
            application_id=application.pk,
            reviewer=self.staff,
            cleaned_data={
                'status': VerificationApplication.STATUS_REJECTED,
                'phone_status': VerificationApplication.CHECK_REJECTED,
                'face_status': VerificationApplication.CHECK_REJECTED,
                'reason': 'Please complete the required checks.',
            },
        )
        self.client.force_login(self.worker)
        url = reverse('verification:worker_application')

        self.client.post(url, {'confirmation': 'on'})
        self.client.post(url, {'confirmation': 'on'})

        application.refresh_from_db()
        self.assertEqual(application.status, VerificationApplication.STATUS_PENDING)
        self.assertEqual(application.decision_reason, '')
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.staff,
                event_key=(
                    f'verification-application:{application.pk}:'
                    'resubmission:1:admin'
                ),
            ).count(),
            1,
        )

    def test_shopkeeper_submission_is_owner_scoped_and_keeps_shop_inactive(self):
        other_shopkeeper = get_user_model().objects.create_user(
            username='verification-other-shopkeeper',
        )
        other_shopkeeper.groups.add(self.shopkeeper_group)
        self.client.force_login(other_shopkeeper)
        response = self.client.post(
            reverse(
                'verification:shopkeeper_application',
                args=[self.shop.pk],
            ),
            {'confirmation': 'on'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            VerificationApplication.objects.filter(shop=self.shop).exists()
        )

        self.client.force_login(self.shopkeeper)
        response = self.client.post(
            reverse(
                'verification:shopkeeper_application',
                args=[self.shop.pk],
            ),
            {'confirmation': 'on'},
        )
        self.assertRedirects(
            response,
            reverse(
                'verification:shopkeeper_application',
                args=[self.shop.pk],
            ),
            fetch_redirect_response=False,
        )
        application = VerificationApplication.objects.get(shop=self.shop)
        self.assertEqual(application.applicant, self.shopkeeper)
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.is_active)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.staff,
                event_key=f'verification-application:{application.pk}:created:admin',
            ).exists()
        )

    def test_shopkeeper_can_resubmit_after_staff_requests_additional_information(self):
        application = VerificationApplication.objects.create(
            applicant=self.shopkeeper,
            shop=self.shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            pan_status=VerificationApplication.CHECK_PENDING,
        )
        review_application(
            application_id=application.pk,
            reviewer=self.staff,
            cleaned_data={
                'status': VerificationApplication.STATUS_INFO_NEEDED,
                'phone_status': VerificationApplication.CHECK_VERIFIED,
                'aadhaar_status': VerificationApplication.CHECK_NOT_SUBMITTED,
                'pan_status': VerificationApplication.CHECK_PENDING,
                'bank_status': VerificationApplication.CHECK_NOT_SUBMITTED,
                'reason': 'Upload a clearer PAN document.',
            },
        )
        self.client.force_login(self.shopkeeper)

        response = self.client.post(
            reverse(
                'verification:shopkeeper_application',
                args=[self.shop.pk],
            ),
            {'confirmation': 'on'},
        )

        self.assertRedirects(
            response,
            reverse(
                'verification:shopkeeper_application',
                args=[self.shop.pk],
            ),
            fetch_redirect_response=False,
        )
        application.refresh_from_db()
        self.assertEqual(application.status, VerificationApplication.STATUS_PENDING)
        self.assertEqual(application.pan_status, VerificationApplication.CHECK_PENDING)
        self.assertEqual(application.decision_reason, '')
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.staff,
                event_key=(
                    f'verification-application:{application.pk}:'
                    'resubmission:1:admin'
                ),
            ).exists()
        )

    def test_shopkeeper_phone_is_verified_only_after_staff_confirms_a_profile_number(self):
        self.shopkeeper.profile.delete()
        application = VerificationApplication.objects.create(
            applicant=self.shopkeeper,
            shop=self.shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
        )
        with self.assertRaisesMessage(
            ValidationError,
            'Add a valid mobile number to the profile before verifying it.',
        ):
            review_application(
                application_id=application.pk,
                reviewer=self.staff,
                cleaned_data={
                    'status': VerificationApplication.STATUS_APPROVED,
                    'phone_status': VerificationApplication.CHECK_VERIFIED,
                    'aadhaar_status': VerificationApplication.CHECK_VERIFIED,
                    'pan_status': VerificationApplication.CHECK_NOT_SUBMITTED,
                    'bank_status': VerificationApplication.CHECK_NOT_SUBMITTED,
                    'reason': 'A mobile number must be supplied first.',
                },
            )

        profile = Profile.objects.create(
            user=self.shopkeeper,
            phone='+15550100002',
        )
        decision = review_application(
            application_id=application.pk,
            reviewer=self.staff,
            cleaned_data={
                'status': VerificationApplication.STATUS_APPROVED,
                'phone_status': VerificationApplication.CHECK_VERIFIED,
                'aadhaar_status': VerificationApplication.CHECK_VERIFIED,
                'pan_status': VerificationApplication.CHECK_NOT_SUBMITTED,
                'bank_status': VerificationApplication.CHECK_NOT_SUBMITTED,
                'reason': 'Mobile and identity documents verified.',
            },
        )

        profile.refresh_from_db()
        self.shop.refresh_from_db()
        self.assertTrue(profile.phone_verified)
        self.assertTrue(self.shop.is_active)
        self.assertEqual(decision.status, VerificationApplication.STATUS_APPROVED)

    def test_changing_verified_shopkeeper_phone_suspends_shop_until_review(self):
        profile = self.shopkeeper.profile
        profile.phone = '+15550100007'
        profile.phone_verified = True
        profile.save()
        application = VerificationApplication.objects.create(
            applicant=self.shopkeeper,
            shop=self.shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
            status=VerificationApplication.STATUS_APPROVED,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            aadhaar_status=VerificationApplication.CHECK_VERIFIED,
        )
        self.shop.is_active = True
        self.shop.save(update_fields=('is_active',))

        profile.phone = '+15550100008'
        profile.save()

        profile.refresh_from_db()
        application.refresh_from_db()
        self.shop.refresh_from_db()
        self.assertFalse(profile.phone_verified)
        self.assertEqual(application.status, VerificationApplication.STATUS_PENDING)
        self.assertEqual(
            application.phone_status,
            VerificationApplication.CHECK_PENDING,
        )
        self.assertFalse(self.shop.is_active)

    def test_non_shopkeeper_cannot_submit_worker_application(self):
        self.client.force_login(self.shopkeeper)

        response = self.client.post(
            reverse('verification:worker_application'),
            {'confirmation': 'on'},
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            VerificationApplication.objects.filter(
                applicant=self.shopkeeper,
            ).exists()
        )

    def test_staff_review_access_remains_required(self):
        application = VerificationApplication.objects.create(
            applicant=self.worker,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
        )
        self.client.force_login(self.worker)
        response = self.client.post(
            reverse(
                'verification:admin_review',
                args=[application.pk],
            ),
            {},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(application.decisions.exists())

        self.client.force_login(self.staff)
        response = self.client.get(
            reverse(
                'verification:admin_review',
                args=[application.pk],
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(application.decisions.exists())

    def test_new_application_notification_and_staff_decision_notify_applicant(self):
        application, submitted = submit_application(
            applicant=self.worker,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
        )
        self.assertTrue(submitted)
        staff_notification = Notification.objects.get(
            recipient=self.staff,
            event_key=f'verification-application:{application.pk}:created:admin',
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

    def test_submission_service_rejects_wrong_applicant_role(self):
        with self.assertRaises(ValidationError):
            submit_application(
                applicant=self.shopkeeper,
                application_type=VerificationApplication.TYPE_REPAIR_WORKER,
            )

    def test_notification_failure_rolls_back_application_submission(self):
        with patch(
            'verification.services.notify_active_staff',
            side_effect=RuntimeError('notification persistence failed'),
        ):
            with self.assertRaises(RuntimeError):
                submit_application(
                    applicant=self.worker,
                    application_type=VerificationApplication.TYPE_REPAIR_WORKER,
                )

        self.assertFalse(
            VerificationApplication.objects.filter(applicant=self.worker).exists()
        )
        self.assertFalse(Notification.objects.exists())
