from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.roles import REPAIR_WORKER_GROUP, user_has_role_group
from .models import VerificationApplication, VerificationDecision


def is_verified_repair_worker(user):
    return (
        user.is_active
        and user_has_role_group(user, REPAIR_WORKER_GROUP)
        and VerificationApplication.objects.filter(
            applicant=user,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
            status=VerificationApplication.STATUS_APPROVED,
            phone_status=VerificationApplication.CHECK_VERIFIED,
            face_status=VerificationApplication.CHECK_VERIFIED,
        ).exists()
    )


@transaction.atomic
def review_application(*, application_id, reviewer, cleaned_data):
    if not reviewer.is_staff:
        raise ValidationError('Only staff can review verification applications.')

    application = VerificationApplication.objects.select_for_update().get(
        pk=application_id,
    )
    status = cleaned_data['status']
    phone_status = cleaned_data['phone_status']
    aadhaar_status = cleaned_data.get(
        'aadhaar_status',
        application.aadhaar_status,
    )
    pan_status = cleaned_data.get('pan_status', application.pan_status)
    bank_status = cleaned_data.get('bank_status', application.bank_status)
    face_status = cleaned_data.get('face_status', application.face_status)
    reason = cleaned_data['reason'].strip()

    if not reason:
        raise ValidationError('A review reason is required.')

    if status == VerificationApplication.STATUS_APPROVED:
        if phone_status != VerificationApplication.CHECK_VERIFIED:
            raise ValidationError('Phone verification is required for approval.')
        if application.application_type == VerificationApplication.TYPE_SHOPKEEPER:
            if not (
                aadhaar_status == VerificationApplication.CHECK_VERIFIED
                or pan_status == VerificationApplication.CHECK_VERIFIED
            ):
                raise ValidationError(
                    'Verify Aadhaar or PAN before approving this shop.'
                )
        elif face_status != VerificationApplication.CHECK_VERIFIED:
            raise ValidationError(
                'Phone and face verification are required for worker approval.'
            )

    if (
        application.application_type == VerificationApplication.TYPE_REPAIR_WORKER
        and status != VerificationApplication.STATUS_APPROVED
    ):
        from bookings.models import RepairBooking

        active_jobs = RepairBooking.objects.filter(
            assigned_worker=application.applicant,
        ).exclude(
            status__in=(
                RepairBooking.STATUS_COMPLETED,
                RepairBooking.STATUS_REJECTED,
            ),
        )
        if active_jobs.exists():
            raise ValidationError(
                'Reassign this worker’s active bookings before revoking approval.'
            )

    application.status = status
    application.phone_status = phone_status
    application.aadhaar_status = aadhaar_status
    application.pan_status = pan_status
    application.bank_status = bank_status
    application.face_status = face_status
    application.decision_reason = reason
    application.reviewed_by = reviewer
    application.save(
        update_fields=(
            'status',
            'phone_status',
            'aadhaar_status',
            'pan_status',
            'bank_status',
            'face_status',
            'decision_reason',
            'reviewed_by',
            'updated_at',
        )
    )

    if application.shop_id:
        application.shop.is_active = (
            status == VerificationApplication.STATUS_APPROVED
        )
        application.shop.save(update_fields=('is_active', 'updated_at'))

    return VerificationDecision.objects.create(
        application=application,
        reviewer=reviewer,
        status=status,
        phone_status=phone_status,
        aadhaar_status=aadhaar_status,
        pan_status=pan_status,
        bank_status=bank_status,
        face_status=face_status,
        reason=reason,
    )
