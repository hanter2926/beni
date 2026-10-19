from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse

from .models import Notification

DESTINATION_ARGUMENT_COUNTS = {
    'customers:orders': 0,
    'customers:order_detail': 1,
    'shopkeeper_order_detail': 1,
    'bookings:customer_detail': 1,
    'bookings:worker_list': 0,
    'bookings:admin_list': 0,
    'verification:admin_list': 0,
    'verification:worker_application': 0,
    'verification:shopkeeper_application': 1,
    'payments:cancellation_queue': 0,
}


def create_notification(
    *,
    recipient,
    event_key,
    title,
    message,
    destination_name,
    destination_args=(),
):
    if not connection.in_atomic_block:
        raise RuntimeError(
            'Notifications must be created inside the business transaction.'
        )
    expected_args = DESTINATION_ARGUMENT_COUNTS.get(destination_name)
    if expected_args is None or len(destination_args) != expected_args:
        raise ValueError('The notification destination is not permitted.')

    destination_url = reverse(destination_name, args=destination_args)
    if not destination_url.startswith('/') or destination_url.startswith('//'):
        raise ValueError('Notification destinations must be local paths.')

    notification, _ = Notification.objects.get_or_create(
        recipient=recipient,
        event_key=event_key,
        defaults={
            'title': title,
            'message': message,
            'destination_url': destination_url,
        },
    )
    return notification


def notify_active_staff(*, event_key, title, message, destination_name, destination_args=()):
    user_model = get_user_model()
    for staff_user in user_model.objects.filter(is_active=True, is_staff=True):
        create_notification(
            recipient=staff_user,
            event_key=event_key,
            title=title,
            message=message,
            destination_name=destination_name,
            destination_args=destination_args,
        )
