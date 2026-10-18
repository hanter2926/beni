from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from accounts.roles import REPAIR_WORKER_GROUP, SHOPKEEPER_GROUP, role_group_required
from notifications.services import notify_active_staff
from shops.models import Shop

from .forms import VerificationReviewForm
from .models import VerificationApplication
from .services import review_application


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_application(request, shop_id):
    shop = get_object_or_404(Shop, pk=shop_id, owner=request.user)
    with transaction.atomic():
        application, created = VerificationApplication.objects.get_or_create(
            applicant=request.user,
            shop=shop,
            application_type=VerificationApplication.TYPE_SHOPKEEPER,
        )
        if created:
            notify_active_staff(
                event_key=f'verification-application:{application.pk}:created:admin',
                title='Shop verification needs review',
                message='A Shopkeeper submitted an application for review.',
                destination_name='verification:admin_list',
            )
    if request.method == 'POST':
        if application.status == VerificationApplication.STATUS_APPROVED:
            messages.info(request, 'This shop is already approved.')
        else:
            if application.status == VerificationApplication.STATUS_REJECTED:
                with transaction.atomic():
                    application.status = VerificationApplication.STATUS_PENDING
                    application.phone_status = VerificationApplication.CHECK_PENDING
                    application.aadhaar_status = (
                        VerificationApplication.CHECK_NOT_SUBMITTED
                    )
                    application.pan_status = VerificationApplication.CHECK_NOT_SUBMITTED
                    application.bank_status = VerificationApplication.CHECK_NOT_SUBMITTED
                    application.face_status = (
                        VerificationApplication.CHECK_NOT_SUBMITTED
                    )
                    application.decision_reason = ''
                    application.reviewed_by = None
                    application.save()
                    submission_number = application.decisions.count()
                    notify_active_staff(
                        event_key=(
                            f'verification-application:{application.pk}:'
                            f'resubmission:{submission_number}:admin'
                        ),
                        title='Shop verification needs review',
                        message='A Shopkeeper resubmitted an application for review.',
                        destination_name='verification:admin_list',
                    )
            messages.success(
                request,
                'Verification application submitted for staff review.',
            )
        return redirect(
            'verification:shopkeeper_application',
            shop_id=shop.pk,
        )

    return render(
        request,
        'shopkeeper/verification/form.html',
        {
            'shop': shop,
            'application': application,
            'role_label': 'Shopkeeper',
        },
    )


@role_group_required(REPAIR_WORKER_GROUP)
def worker_application(request):
    with transaction.atomic():
        application, created = VerificationApplication.objects.get_or_create(
            applicant=request.user,
            application_type=VerificationApplication.TYPE_REPAIR_WORKER,
            shop=None,
            defaults={
                'phone_status': VerificationApplication.CHECK_PENDING,
                'face_status': VerificationApplication.CHECK_PENDING,
            },
        )
        if created:
            notify_active_staff(
                event_key=f'verification-application:{application.pk}:created:admin',
                title='Repair Worker verification needs review',
                message='A Repair Worker submitted an application for review.',
                destination_name='verification:admin_list',
            )
    if request.method == 'POST':
        if application.status == VerificationApplication.STATUS_APPROVED:
            messages.info(request, 'Your Repair Worker account is already approved.')
        else:
            if application.status == VerificationApplication.STATUS_REJECTED:
                with transaction.atomic():
                    application.status = VerificationApplication.STATUS_PENDING
                    application.phone_status = VerificationApplication.CHECK_PENDING
                    application.face_status = VerificationApplication.CHECK_PENDING
                    application.decision_reason = ''
                    application.reviewed_by = None
                    application.save()
                    submission_number = application.decisions.count()
                    notify_active_staff(
                        event_key=(
                            f'verification-application:{application.pk}:'
                            f'resubmission:{submission_number}:admin'
                        ),
                        title='Repair Worker verification needs review',
                        message='A Repair Worker resubmitted an application for review.',
                        destination_name='verification:admin_list',
                    )
            messages.success(
                request,
                'Verification application submitted for staff review.',
            )
        return redirect('verification:worker_application')

    return render(
        request,
        'repair_worker/verification/form.html',
        {'application': application, 'role_label': 'Repair worker'},
    )


@staff_member_required(login_url='accounts:login')
def admin_application_list(request):
    applications = list(
        VerificationApplication.objects.select_related(
            'applicant',
            'shop',
            'reviewed_by',
        ).prefetch_related('decisions')
    )
    for application in applications:
        application.review_form = VerificationReviewForm(
            application_type=application.application_type,
            initial={
                'status': application.status,
                'phone_status': application.phone_status,
                'aadhaar_status': application.aadhaar_status,
                'pan_status': application.pan_status,
                'bank_status': application.bank_status,
                'face_status': application.face_status,
                'reason': application.decision_reason,
            }
        )
    return render(
        request,
        'admin_panel/verification/list.html',
        {'applications': applications, 'role_label': 'Admin'},
    )


@staff_member_required(login_url='accounts:login')
def admin_application_review(request, application_id):
    if request.method != 'POST':
        raise PermissionDenied
    application = get_object_or_404(
        VerificationApplication,
        pk=application_id,
    )
    form = VerificationReviewForm(
        request.POST,
        application_type=application.application_type,
    )
    if not form.is_valid():
        messages.error(request, 'Correct the verification review fields.')
        return redirect('verification:admin_list')

    try:
        review_application(
            application_id=application.pk,
            reviewer=request.user,
            cleaned_data=form.cleaned_data,
        )
    except ValidationError as exc:
        messages.error(request, ' '.join(exc.messages))
    else:
        messages.success(request, 'Verification decision recorded.')
    return redirect('verification:admin_list')
