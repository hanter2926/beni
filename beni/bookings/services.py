from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.roles import REPAIR_WORKER_GROUP, user_has_role_group
from notifications.services import create_notification
from verification.models import VerificationApplication
from .models import BookingAssignmentEvent, RepairBooking


class BookingTransitionError(Exception):
    pass


def _lock_verified_worker_application(worker):
    if (
        not worker.is_active
        or not user_has_role_group(worker, REPAIR_WORKER_GROUP)
    ):
        return False
    return VerificationApplication.objects.select_for_update().filter(
        applicant=worker,
        application_type=VerificationApplication.TYPE_REPAIR_WORKER,
        status=VerificationApplication.STATUS_APPROVED,
        phone_status=VerificationApplication.CHECK_VERIFIED,
        face_status=VerificationApplication.CHECK_VERIFIED,
    ).first() is not None


WORKER_TRANSITIONS = {
    RepairBooking.STATUS_ASSIGNED: {
        RepairBooking.STATUS_ACCEPTED,
        RepairBooking.STATUS_REJECTED,
    },
    RepairBooking.STATUS_ACCEPTED: {RepairBooking.STATUS_IN_PROGRESS},
    RepairBooking.STATUS_IN_PROGRESS: {RepairBooking.STATUS_COMPLETED},
}


@transaction.atomic
def assign_worker(*, booking_id, worker, actor):
    if not actor.is_staff:
        raise BookingTransitionError('Only staff can assign repair workers.')
    if not _lock_verified_worker_application(worker):
        raise BookingTransitionError(
            'Choose an active, verified Repair Worker.'
        )

    booking = (
        RepairBooking.objects.select_for_update()
        .select_related('customer', 'assigned_worker')
        .get(pk=booking_id)
    )
    if booking.status not in (
        RepairBooking.STATUS_REQUESTED,
        RepairBooking.STATUS_REJECTED,
    ):
        raise BookingTransitionError(
            'This booking cannot be assigned in its current status.'
        )

    previous_worker = booking.assigned_worker
    if previous_worker is None:
        previous_assignment = (
            booking.assignment_events.select_related('assigned_worker')
            .order_by('-created_at', '-pk')
            .first()
        )
        if previous_assignment is not None:
            previous_worker = previous_assignment.assigned_worker
    booking.assigned_worker = worker
    booking.status = RepairBooking.STATUS_ASSIGNED
    booking.save(update_fields=('assigned_worker', 'status', 'updated_at'))
    assignment = BookingAssignmentEvent.objects.create(
        booking=booking,
        assigned_worker=worker,
        previous_worker=previous_worker,
        assigned_by=actor,
    )
    create_notification(
        recipient=worker,
        event_key=f'booking-assignment:{assignment.pk}:worker',
        title='Repair job assigned',
        message='A repair job has been assigned to you.',
        destination_name='bookings:worker_list',
    )
    create_notification(
        recipient=booking.customer,
        event_key=f'booking-assignment:{assignment.pk}:customer',
        title='Repair worker assigned',
        message='A Repair Worker has been assigned to your repair request.',
        destination_name='bookings:customer_detail',
        destination_args=(booking.pk,),
    )
    if previous_worker and previous_worker.pk != worker.pk:
        create_notification(
            recipient=previous_worker,
            event_key=f'booking-assignment:{assignment.pk}:previous-worker',
            title='Repair job reassigned',
            message='A repair job has been reassigned.',
            destination_name='bookings:worker_list',
        )
    return booking


@transaction.atomic
def transition_worker_booking(*, booking_id, worker, new_status):
    if not _lock_verified_worker_application(worker):
        raise BookingTransitionError(
            'Your Repair Worker verification is not approved.'
        )
    booking = RepairBooking.objects.select_for_update().filter(
        pk=booking_id,
        assigned_worker=worker,
    ).first()
    if booking is None:
        return None

    allowed = WORKER_TRANSITIONS.get(booking.status, set())
    if new_status not in allowed:
        raise BookingTransitionError(
            'That repair booking status change is not allowed.'
        )

    old_status = booking.status
    booking.status = new_status
    if new_status == RepairBooking.STATUS_REJECTED:
        booking.assigned_worker = None
        booking.save(update_fields=('status', 'assigned_worker', 'updated_at'))
    else:
        booking.save(update_fields=('status', 'updated_at'))
    assignment_id = (
        booking.assignment_events.order_by('-created_at', '-pk')
        .values_list('pk', flat=True)
        .first()
    )
    event_version = assignment_id or booking.updated_at.isoformat()
    create_notification(
        recipient=booking.customer,
        event_key=(
            f'booking:{booking.pk}:assignment:{event_version}:'
            f'status:{old_status}:{new_status}:customer'
        ),
        title='Repair request updated',
        message=(
            f'Your repair request is now {booking.get_status_display().lower()}.'
        ),
        destination_name='bookings:customer_detail',
        destination_args=(booking.pk,),
    )
    return booking


def active_repair_workers():
    user_model = get_user_model()
    return user_model.objects.filter(is_active=True, groups__name=REPAIR_WORKER_GROUP).filter(
        verification_applications__application_type=(
            VerificationApplication.TYPE_REPAIR_WORKER
        ),
        verification_applications__status=VerificationApplication.STATUS_APPROVED,
        verification_applications__phone_status=(
            VerificationApplication.CHECK_VERIFIED
        ),
        verification_applications__face_status=(
            VerificationApplication.CHECK_VERIFIED
        ),
    ).distinct()
