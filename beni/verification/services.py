from django.core.exceptions import ValidationError
from django.db import transaction

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    user_has_role_group,
)
from accounts.models import Profile, valid_phone_number
from notifications.services import create_notification, notify_active_staff
from .models import VerificationApplication, VerificationDecision


@transaction.atomic
def submit_application(*, applicant, application_type, shop=None):
    if application_type == VerificationApplication.TYPE_SHOPKEEPER:
        if (
            shop is None
            or shop.owner_id != applicant.pk
            or not user_has_role_group(applicant, SHOPKEEPER_GROUP)
        ):
            raise ValidationError(
                'A Shopkeeper can submit verification only for their own shop.'
            )
        lookup = {
            'applicant': applicant,
            'shop': shop,
            'application_type': application_type,
        }
        defaults = {}
        title = 'Shop verification needs review'
        message = 'A Shopkeeper submitted an application for review.'
    elif application_type == VerificationApplication.TYPE_REPAIR_WORKER:
        if shop is not None or not user_has_role_group(
            applicant,
            REPAIR_WORKER_GROUP,
        ):
            raise ValidationError('Only a Repair Worker can submit worker verification.')
        lookup = {
            'applicant': applicant,
            'application_type': application_type,
            'shop': None,
        }
        defaults = {
            'phone_status': VerificationApplication.CHECK_PENDING,
            'face_status': VerificationApplication.CHECK_PENDING,
        }
        title = 'Repair Worker verification needs review'
        message = 'A Repair Worker submitted an application for review.'
    else:
        raise ValidationError('The verification application type is invalid.')

    if application_type == VerificationApplication.TYPE_SHOPKEEPER:
        profile = Profile.objects.select_for_update().filter(
            user=applicant,
        ).first()
        if profile is None or not valid_phone_number(profile.phone):
            raise ValidationError(
                'Add a valid mobile number to your account profile before submitting.'
            )

    application = VerificationApplication.objects.select_for_update().filter(
        **lookup,
    ).first()
    created = False
    if application is None:
        application, created = VerificationApplication.objects.get_or_create(
            **lookup,
            defaults=defaults,
        )
        if not created:
            application = VerificationApplication.objects.select_for_update().get(
                pk=application.pk,
            )
    if application.status == VerificationApplication.STATUS_APPROVED:
        return application, False

    previous_status = application.status
    resubmitted = previous_status in (
        VerificationApplication.STATUS_REJECTED,
        VerificationApplication.STATUS_INFO_NEEDED,
    )
    if resubmitted:
        application.status = VerificationApplication.STATUS_PENDING
        application.decision_reason = ''
        application.reviewed_by = None
        update_fields = [
            'status',
            'decision_reason',
            'reviewed_by',
            'updated_at',
        ]
        if application_type == VerificationApplication.TYPE_SHOPKEEPER:
            if previous_status == VerificationApplication.STATUS_REJECTED:
                application.phone_status = VerificationApplication.CHECK_PENDING
                application.aadhaar_status = (
                    VerificationApplication.CHECK_NOT_SUBMITTED
                )
                application.pan_status = VerificationApplication.CHECK_NOT_SUBMITTED
                application.bank_status = VerificationApplication.CHECK_NOT_SUBMITTED
                application.face_status = VerificationApplication.CHECK_NOT_SUBMITTED
                update_fields.extend(
                    (
                        'phone_status',
                        'aadhaar_status',
                        'pan_status',
                        'bank_status',
                        'face_status',
                    )
                )
        else:
            application.phone_status = VerificationApplication.CHECK_PENDING
            application.face_status = VerificationApplication.CHECK_PENDING
            update_fields.extend(('phone_status', 'face_status'))
        application.save(update_fields=update_fields)

    submission_number = application.decisions.count()
    if submission_number:
        event_key = (
            f'verification-application:{application.pk}:'
            f'resubmission:{submission_number}:admin'
        )
        notification_message = (
            f'A {application.get_application_type_display()} '
            'resubmitted an application for review.'
        )
    else:
        event_key = (
            f'verification-application:{application.pk}:created:admin'
        )
        notification_message = message

    notify_active_staff(
        event_key=event_key,
        title=title,
        message=notification_message,
        destination_name='verification:admin_list',
    )
    return application, created or resubmitted


def is_verified_repair_worker(user):
    profile = Profile.objects.filter(user=user).first()
    return (
        user.is_active
        and user_has_role_group(user, REPAIR_WORKER_GROUP)
        and profile is not None
        and profile.phone_verified
        and valid_phone_number(profile.phone)
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
                RepairBooking.STATUS_CANCELLED,
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

    if application.application_type in (
        VerificationApplication.TYPE_SHOPKEEPER,
        VerificationApplication.TYPE_REPAIR_WORKER,
    ):
        profile = Profile.objects.select_for_update().filter(
            user=application.applicant,
        ).first()
        if (
            phone_status == VerificationApplication.CHECK_VERIFIED
            and (profile is None or not valid_phone_number(profile.phone))
        ):
            raise ValidationError(
                'Add a valid mobile number to the profile before verifying it.'
            )
        if profile is not None:
            profile.phone_verified = phone_status == VerificationApplication.CHECK_VERIFIED
            profile.save(update_fields=('phone_verified',))

    if application.shop_id:
        application.shop.is_active = (
            status == VerificationApplication.STATUS_APPROVED
        )
        application.shop.save(update_fields=('is_active', 'updated_at'))

    decision = VerificationDecision.objects.create(
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
    if application.application_type == VerificationApplication.TYPE_REPAIR_WORKER:
        destination_name = 'verification:worker_application'
        destination_args = ()
    else:
        destination_name = 'verification:shopkeeper_application'
        destination_args = (application.shop_id,)
    create_notification(
        recipient=application.applicant,
        event_key=f'verification-decision:{decision.pk}:applicant',
        title='Verification application updated',
        message=(
            f'Your {application.get_application_type_display().lower()} '
            f'application was {application.get_status_display().lower()}.'
        ),
        destination_name=destination_name,
        destination_args=destination_args,
    )
    return decision
