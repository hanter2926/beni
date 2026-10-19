from django.db import transaction

from bookings.models import RepairBooking
from notifications.services import create_notification, notify_active_staff
from orders.models import Order

from .models import Review


class ReviewWorkflowError(Exception):
    pass


@transaction.atomic
def submit_order_review(*, order_number, customer, rating, body):
    order = (
        Order.objects.select_for_update()
        .filter(order_number=order_number, customer=customer)
        .first()
    )
    if order is None:
        return None
    if order.status != Order.STATUS_DELIVERED:
        raise ReviewWorkflowError(
            'An order review is available only after delivery.'
        )
    if Review.objects.filter(order=order).exists():
        raise ReviewWorkflowError('You have already reviewed this order.')

    review = Review.objects.create(
        customer=customer,
        order=order,
        rating=rating,
        body=body,
    )
    notify_active_staff(
        event_key=f'review:{review.pk}:submitted:staff',
        title='Customer review needs moderation',
        message='A customer submitted a shop order review.',
        destination_name='reviews:moderation_queue',
    )
    return review


@transaction.atomic
def submit_repair_review(*, booking_id, customer, rating, body):
    booking = (
        RepairBooking.objects.select_for_update()
        .filter(pk=booking_id, customer=customer)
        .first()
    )
    if booking is None:
        return None
    if (
        booking.status != RepairBooking.STATUS_COMPLETED
        or booking.assigned_worker_id is None
    ):
        raise ReviewWorkflowError(
            'A repair review is available only after a completed assigned repair.'
        )
    if Review.objects.filter(booking=booking).exists():
        raise ReviewWorkflowError('You have already reviewed this repair.')

    review = Review.objects.create(
        customer=customer,
        booking=booking,
        rating=rating,
        body=body,
    )
    notify_active_staff(
        event_key=f'review:{review.pk}:submitted:staff',
        title='Repair review needs moderation',
        message='A customer submitted a repair service review.',
        destination_name='reviews:moderation_queue',
    )
    return review


@transaction.atomic
def moderate_review(*, review_id, moderator, status, moderation_note=''):
    if not moderator.is_staff:
        return None
    review = Review.objects.select_for_update().filter(pk=review_id).first()
    if review is None:
        return None
    if review.status != Review.STATUS_PENDING:
        raise ReviewWorkflowError('This review has already been moderated.')
    if status not in (Review.STATUS_PUBLISHED, Review.STATUS_REJECTED):
        raise ReviewWorkflowError('Choose a valid moderation decision.')
    if status == Review.STATUS_REJECTED and not moderation_note.strip():
        raise ReviewWorkflowError(
            'Add a reason when declining a review.'
        )

    review.status = status
    review.moderator = moderator
    review.moderation_note = moderation_note.strip()
    review.save(
        update_fields=(
            'status',
            'moderator',
            'moderation_note',
            'updated_at',
        )
    )
    result = (
        'published'
        if status == Review.STATUS_PUBLISHED
        else 'not published'
    )
    create_notification(
        recipient=review.customer,
        event_key=f'review:{review.pk}:moderated:{status}:customer',
        title='Your BENI review was moderated',
        message=f'Your review was {result}.',
        destination_name='reviews:customer_list',
    )
    return review
