from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.test import Client, RequestFactory, TestCase, TransactionTestCase
from django.urls import reverse

from .context_processors import unread_notification_count
from .models import Notification
from .services import create_notification


class NotificationInboxTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.recipient = user_model.objects.create_user(username='notice-recipient')
        self.other_user = user_model.objects.create_user(username='notice-other')

    def create_for(self, recipient, event_key):
        with transaction.atomic():
            return create_notification(
                recipient=recipient,
                event_key=event_key,
                title='Order updated',
                message='Your order status changed.',
                destination_name='customers:orders',
            )

    def test_inbox_and_unread_count_are_recipient_scoped(self):
        own_notification = self.create_for(self.recipient, 'order:1:status')
        other_notification = self.create_for(self.other_user, 'order:2:status')
        self.client.force_login(self.recipient)

        response = self.client.get(reverse('notifications:inbox'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_notification.title)
        self.assertNotContains(response, other_notification.title)
        self.assertEqual(response.context['unread_notification_count'], 1)

    def test_duplicate_event_is_idempotent_per_recipient(self):
        first = self.create_for(self.recipient, 'order:1:placed:customer')
        duplicate = self.create_for(self.recipient, 'order:1:placed:customer')

        self.assertEqual(first.pk, duplicate.pk)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.recipient,
                event_key='order:1:placed:customer',
            ).count(),
            1,
        )

    def test_mark_read_is_post_only_and_recipient_scoped(self):
        own_notification = self.create_for(self.recipient, 'own:event')
        other_notification = self.create_for(self.other_user, 'other:event')
        self.client.force_login(self.recipient)
        url = reverse(
            'notifications:mark_read',
            args=[own_notification.pk],
        )

        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(
            self.client.post(
                reverse('notifications:mark_read', args=[other_notification.pk])
            ).status_code,
            404,
        )
        self.assertIsNone(own_notification.read_at)

        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse('notifications:inbox'),
            fetch_redirect_response=False,
        )
        own_notification.refresh_from_db()
        self.assertIsNotNone(own_notification.read_at)

    def test_mark_all_read_only_updates_current_recipient_and_requires_post(self):
        own_notification = self.create_for(self.recipient, 'own:unread')
        other_notification = self.create_for(self.other_user, 'other:unread')
        self.client.force_login(self.recipient)
        url = reverse('notifications:mark_all_read')

        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url)

        self.assertRedirects(
            response,
            reverse('notifications:inbox'),
            fetch_redirect_response=False,
        )
        own_notification.refresh_from_db()
        other_notification.refresh_from_db()
        self.assertIsNotNone(own_notification.read_at)
        self.assertIsNone(other_notification.read_at)

    def test_anonymous_unread_count_does_not_query_notifications(self):
        request = RequestFactory().get('/')
        request.user = AnonymousUser()

        with self.assertNumQueries(0):
            result = unread_notification_count(request)

        self.assertEqual(result, {'unread_notification_count': 0})

    def test_mark_read_requires_csrf(self):
        notification = self.create_for(self.recipient, 'csrf:event')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.recipient)

        response = client.post(
            reverse('notifications:mark_read', args=[notification.pk])
        )

        self.assertEqual(response.status_code, 403)


class NotificationTransactionTests(TransactionTestCase):
    def test_notification_persistence_requires_business_transaction(self):
        recipient = get_user_model().objects.create_user(
            username='notice-transaction-recipient',
        )

        with self.assertRaises(RuntimeError):
            create_notification(
                recipient=recipient,
                event_key='unbound:event',
                title='Not allowed',
                message='No transaction.',
                destination_name='customers:orders',
            )
