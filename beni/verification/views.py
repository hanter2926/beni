from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from accounts.roles import REPAIR_WORKER_GROUP, SHOPKEEPER_GROUP, role_group_required
from beni.private_files import private_document_response
from shops.models import Shop

from .forms import VerificationReviewForm, VerificationSubmissionForm
from .models import VerificationApplication, VerificationDocument
from .services import review_application, submit_application


def _persist_application_documents(*, form, application, applicant):
    for document in form.cleaned_data.get('remove_documents', []):
        document.delete()
    for uploaded_file in form.cleaned_data.get('documents', []):
        VerificationDocument.objects.create(
            application=application,
            uploaded_by=applicant,
            document_type=form.cleaned_data['document_type'],
            file=uploaded_file,
        )


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_application(request, shop_id):
    shop = get_object_or_404(Shop, pk=shop_id, owner=request.user)
    application = VerificationApplication.objects.filter(
        applicant=request.user,
        shop=shop,
        application_type=VerificationApplication.TYPE_SHOPKEEPER,
    ).first()
    form = VerificationSubmissionForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        application=application,
        application_type=VerificationApplication.TYPE_SHOPKEEPER,
    )
    if request.method == 'POST':
        if form.is_valid():
            try:
                application, submitted = submit_application(
                    applicant=request.user,
                    application_type=VerificationApplication.TYPE_SHOPKEEPER,
                    shop=shop,
                )
            except ValidationError as exc:
                form.add_error(None, ' '.join(exc.messages))
            else:
                if application.status != VerificationApplication.STATUS_APPROVED:
                    _persist_application_documents(
                        form=form,
                        application=application,
                        applicant=request.user,
                    )
                if application.status == VerificationApplication.STATUS_APPROVED:
                    messages.info(request, 'This shop is already approved.')
                elif submitted:
                    messages.success(
                        request,
                        'Verification application submitted for staff review.',
                    )
                else:
                    messages.info(
                        request,
                        'Your application is already awaiting staff review.',
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
            'form': form,
            'role_label': 'Shopkeeper',
        },
    )


@role_group_required(REPAIR_WORKER_GROUP)
def worker_application(request):
    application = VerificationApplication.objects.filter(
        applicant=request.user,
        application_type=VerificationApplication.TYPE_REPAIR_WORKER,
        shop=None,
    ).first()
    form = VerificationSubmissionForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        application=application,
        application_type=VerificationApplication.TYPE_REPAIR_WORKER,
    )
    if request.method == 'POST':
        if form.is_valid():
            try:
                application, submitted = submit_application(
                    applicant=request.user,
                    application_type=VerificationApplication.TYPE_REPAIR_WORKER,
                )
            except ValidationError as exc:
                form.add_error(None, ' '.join(exc.messages))
            else:
                if application.status != VerificationApplication.STATUS_APPROVED:
                    _persist_application_documents(
                        form=form,
                        application=application,
                        applicant=request.user,
                    )
                if application.status == VerificationApplication.STATUS_APPROVED:
                    messages.info(
                        request,
                        'Your Repair Worker account is already approved.',
                    )
                elif submitted:
                    messages.success(
                        request,
                        'Verification application submitted for staff review.',
                    )
                else:
                    messages.info(
                        request,
                        'Your application is already awaiting staff review.',
                    )
                return redirect('verification:worker_application')

    return render(
        request,
        'repair_worker/verification/form.html',
        {
            'application': application,
            'form': form,
            'role_label': 'Repair worker',
        },
    )


@staff_member_required(login_url='accounts:login')
def admin_application_list(request):
    applications = list(
        VerificationApplication.objects.select_related(
            'applicant',
            'shop',
            'reviewed_by',
        ).prefetch_related('decisions', 'documents')
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


@staff_member_required(login_url='accounts:login')
@require_GET
def admin_document(_request, document_id):
    document = get_object_or_404(
        VerificationDocument.objects.select_related('application'),
        pk=document_id,
    )
    return private_document_response(document.file)
