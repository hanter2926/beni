from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.roles import REPAIR_WORKER_GROUP, user_has_role_group
from verification.models import VerificationApplication
from .models import RepairBooking


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

    booking = RepairBooking.objects.select_for_update().get(pk=booking_id)
    if booking.status not in (
        RepairBooking.STATUS_REQUESTED,
        RepairBooking.STATUS_REJECTED,
    ):
        raise BookingTransitionError(
            'This booking cannot be assigned in its current status.'
        )

    booking.assigned_worker = worker
    booking.status = RepairBooking.STATUS_ASSIGNED
    booking.save(update_fields=('assigned_worker', 'status', 'updated_at'))
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

    booking.status = new_status
    if new_status == RepairBooking.STATUS_REJECTED:
        booking.assigned_worker = None
        booking.save(update_fields=('status', 'assigned_worker', 'updated_at'))
    else:
        booking.save(update_fields=('status', 'updated_at'))
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
