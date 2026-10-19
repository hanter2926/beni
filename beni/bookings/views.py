from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import valid_phone_number
from accounts.roles import REPAIR_WORKER_GROUP, role_group_required
from beni.private_files import private_image_response
from customers.views import is_customer_user
from notifications.services import create_notification, notify_active_staff

from .forms import (
    BookingImageForm,
    BookingSupportRequestForm,
    RepairBookingForm,
    WorkerAssignmentForm,
    WorkerBookingStatusForm,
)
from .models import RepairBooking, RepairBookingImage
from .services import (
    BookingTransitionError,
    active_repair_workers,
    assign_worker,
    cancel_customer_booking,
    submit_support_request,
    transition_worker_booking,
)
from verification.services import is_verified_repair_worker

def _customer_only(request):
    if not is_customer_user(request.user):
        raise PermissionDenied


def _phone_actions(phone):
    if not valid_phone_number(phone):
        return None, None
    digits = ''.join(character for character in phone if character.isdigit())
    tel_url = f'tel:{("+" if phone.strip().startswith("+") else "")}{digits}'
    whatsapp_url = (
        f'https://wa.me/{digits}'
        if phone.strip().startswith('+') and 7 <= len(digits) <= 15
        else None
    )
    return tel_url, whatsapp_url


def _set_booking_contact(booking, *, participant, is_worker=False):
    profile = getattr(participant, 'profile', None)
    available = (
        booking.status in RepairBooking.CONTACT_ALLOWED_STATUSES
        and booking.assigned_worker_id is not None
        and profile is not None
        and profile.phone_verified
        and valid_phone_number(profile.phone)
        and (not is_worker or is_verified_repair_worker(participant))
    )
    phone = profile.phone if available else ''
    tel_url, whatsapp_url = _phone_actions(phone)
    booking.contact_phone = phone
    booking.contact_alternate_phone = (
        profile.alternate_phone
        if phone and valid_phone_number(profile.alternate_phone)
        else ''
    )
    booking.contact_tel_url = tel_url
    booking.contact_whatsapp_url = whatsapp_url
    booking.contact_verified = bool(phone)


def _support_form():
    return BookingSupportRequestForm()


def _save_booking_images(*, booking, uploaded_by, image_type, images):
    for image in images:
        RepairBookingImage.objects.create(
            booking=booking,
            uploaded_by=uploaded_by,
            image_type=image_type,
            image=image,
        )


def _remove_booking_images(images):
    for image_record in images:
        image_record.delete()


@login_required(login_url='accounts:login')
def customer_booking_list(request):
    _customer_only(request)
    bookings = RepairBooking.objects.filter(customer=request.user)
    return render(
        request,
        'customer/repairs/list.html',
        {'bookings': bookings, 'role_label': 'Customer'},
    )


@login_required(login_url='accounts:login')
def customer_booking_create(request):
    _customer_only(request)
    profile = getattr(request.user, 'profile', None)
    if (
        profile is None
        or not profile.phone_verified
        or not valid_phone_number(profile.phone)
    ):
        messages.error(
            request,
            'Add your mobile number to your profile and ask BENI staff to verify it before requesting a repair.',
        )
        return redirect('accounts:profile')
    form = RepairBookingForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
    )
    if request.method == 'POST' and form.is_valid():
        uploaded_images = form.cleaned_data.get('images', [])
        with transaction.atomic():
            booking = form.save(commit=False)
            booking.customer = request.user
            booking.save()
            _save_booking_images(
                booking=booking,
                uploaded_by=request.user,
                image_type=RepairBookingImage.TYPE_CUSTOMER_CONDITION,
                images=uploaded_images,
            )
            create_notification(
                recipient=request.user,
                event_key=f'booking:{booking.pk}:created:customer',
                title='Repair request submitted',
                message='Your repair request was submitted.',
                destination_name='bookings:customer_detail',
                destination_args=(booking.pk,),
            )
            notify_active_staff(
                event_key=f'booking:{booking.pk}:created:admin',
                title='Repair request needs assignment',
                message='A customer submitted a repair request.',
                destination_name='bookings:admin_list',
            )
        messages.success(request, 'Your repair request was submitted.')
        return redirect('bookings:customer_detail', booking_id=booking.pk)

    return render(
        request,
        'customer/repairs/form.html',
        {'form': form, 'role_label': 'Customer'},
    )


@login_required(login_url='accounts:login')
def customer_booking_detail(request, booking_id):
    _customer_only(request)
    booking = get_object_or_404(
        RepairBooking.objects.select_related(
            'assigned_worker',
            'assigned_worker__profile',
        ).prefetch_related(
            'images',
        ),
        pk=booking_id,
        customer=request.user,
    )
    image_form = BookingImageForm(
        request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None,
        booking=booking,
        actor=request.user,
        image_types=(RepairBookingImage.TYPE_CUSTOMER_CONDITION,),
    )
    if request.method == 'POST':
        if image_form.is_valid():
            _remove_booking_images(image_form.cleaned_data.get('remove_images', []))
            _save_booking_images(
                booking=booking,
                uploaded_by=request.user,
                image_type=RepairBookingImage.TYPE_CUSTOMER_CONDITION,
                images=image_form.cleaned_data.get('images', []),
            )
            if image_form.cleaned_data.get('images') or image_form.cleaned_data.get('remove_images'):
                messages.success(request, 'Repair photos updated.')
            return redirect('bookings:customer_detail', booking_id=booking.pk)
        messages.error(request, 'Correct the repair photo fields and try again.')
        booking = get_object_or_404(
            RepairBooking.objects.select_related(
                'assigned_worker',
                'assigned_worker__profile',
            ).prefetch_related(
                'images',
            ),
            pk=booking_id,
            customer=request.user,
        )
    if booking.assigned_worker_id:
        _set_booking_contact(
            booking,
            participant=booking.assigned_worker,
            is_worker=True,
        )
        booking.worker_profile = getattr(
            booking.assigned_worker,
            'profile',
            None,
        )
    return render(
        request,
        'customer/repairs/detail.html',
        {
            'booking': booking,
            'image_form': image_form,
            'support_form': _support_form(),
            'can_cancel': booking.status in (
                RepairBooking.STATUS_REQUESTED,
                RepairBooking.STATUS_ASSIGNED,
                RepairBooking.STATUS_ACCEPTED,
            ),
            'role_label': 'Customer',
        },
    )


@role_group_required(REPAIR_WORKER_GROUP)
def worker_booking_list(request):
    if not is_verified_repair_worker(request.user):
        raise PermissionDenied
    bookings = list(
        RepairBooking.objects.filter(assigned_worker=request.user)
        .select_related('customer', 'customer__profile')
        .prefetch_related('images')
    )
    for booking in bookings:
        _set_booking_contact(booking, participant=booking.customer)
        booking.support_form = _support_form()
        booking.status_form = WorkerBookingStatusForm(
            current_status=booking.status,
            booking=booking,
            actor=request.user,
        )
    return render(
        request,
        'repair_worker/repairs/list.html',
        {
            'bookings': bookings,
            'role_label': 'Repair worker',
        },
    )


@require_POST
@login_required(login_url='accounts:login')
def customer_booking_cancel(request, booking_id):
    _customer_only(request)
    try:
        booking = cancel_customer_booking(
            booking_id=booking_id,
            customer=request.user,
        )
    except BookingTransitionError as exc:
        messages.error(request, str(exc))
        return redirect('bookings:customer_detail', booking_id=booking_id)
    if booking is None:
        raise Http404
    messages.success(request, 'Your repair request was cancelled.')
    return redirect('bookings:customer_detail', booking_id=booking.pk)


@require_POST
@login_required(login_url='accounts:login')
def booking_support_request(request, booking_id):
    booking = get_object_or_404(
        RepairBooking.objects.select_related('assigned_worker'),
        pk=booking_id,
    )
    customer_is_reporter = booking.customer_id == request.user.pk
    worker_is_reporter = (
        booking.assigned_worker_id == request.user.pk
        and is_verified_repair_worker(request.user)
    )
    if not (customer_is_reporter or worker_is_reporter):
        raise Http404
    form = BookingSupportRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Correct the support request fields and try again.')
    else:
        support_request = submit_support_request(
            booking_id=booking.pk,
            reporter=request.user,
            request_type=form.cleaned_data['request_type'],
            description=form.cleaned_data['description'],
        )
        if support_request is None:
            raise Http404
        messages.success(request, 'Your support request was sent to BENI staff.')
    if customer_is_reporter:
        return redirect('bookings:customer_detail', booking_id=booking.pk)
    return redirect('bookings:worker_list')


@require_POST
@role_group_required(REPAIR_WORKER_GROUP)
def worker_booking_update(request, booking_id):
    if not is_verified_repair_worker(request.user):
        raise PermissionDenied
    booking = get_object_or_404(
        RepairBooking,
        pk=booking_id,
        assigned_worker=request.user,
    )
    form = WorkerBookingStatusForm(
        request.POST,
        current_status=booking.status,
        booking=booking,
        actor=request.user,
    )
    if not form.is_valid():
        messages.error(request, 'Correct the job update fields and try again.')
        return redirect('bookings:worker_list')

    if form.cleaned_data.get('status'):
        try:
            changed = transition_worker_booking(
                booking_id=booking.pk,
                worker=request.user,
                new_status=form.cleaned_data['status'],
            )
        except BookingTransitionError as exc:
            messages.error(request, str(exc))
            return redirect('bookings:worker_list')
        if changed is None:
            messages.error(request, 'That assigned job could not be found.')
            return redirect('bookings:worker_list')
    _remove_booking_images(form.cleaned_data.get('remove_images', []))
    _save_booking_images(
        booking=booking,
        uploaded_by=request.user,
        image_type=form.cleaned_data.get('image_type'),
        images=form.cleaned_data.get('images', []),
    )
    if form.cleaned_data.get('status'):
        messages.success(request, 'Repair job status updated.')
    elif form.cleaned_data.get('images') or form.cleaned_data.get('remove_images'):
        messages.success(request, 'Repair job photos updated.')

    return redirect('bookings:worker_list')


@login_required(login_url='accounts:login')
def private_booking_image(request, image_id):
    image_record = get_object_or_404(
        RepairBookingImage.objects.select_related('booking'),
        pk=image_id,
    )
    booking = image_record.booking
    if not (
        request.user.is_staff
        or booking.customer_id == request.user.pk
        or booking.assigned_worker_id == request.user.pk
    ):
        raise Http404
    return private_image_response(image_record.image)


@staff_member_required(login_url='accounts:login')
def admin_booking_list(request):
    unassigned_only = request.GET.get('assignment') == 'unassigned'
    booking_queryset = RepairBooking.objects.select_related(
        'customer',
        'customer__profile',
        'assigned_worker',
        'assigned_worker__profile',
    ).prefetch_related('images', 'support_requests__reporter')
    if unassigned_only:
        booking_queryset = booking_queryset.filter(assigned_worker__isnull=True)
    bookings = list(booking_queryset)
    for booking in bookings:
        booking.customer_profile = getattr(booking.customer, 'profile', None)
        booking.worker_profile = (
            getattr(booking.assigned_worker, 'profile', None)
            if booking.assigned_worker_id
            else None
        )
        booking.assignment_form = WorkerAssignmentForm()
        booking.can_assign = booking.status in (
            RepairBooking.STATUS_REQUESTED,
            RepairBooking.STATUS_REJECTED,
        )
    return render(
        request,
        'admin_panel/repairs/list.html',
        {
            'bookings': bookings,
            'unassigned_only': unassigned_only,
            'role_label': 'Admin',
        },
    )


@require_POST
@staff_member_required(login_url='accounts:login')
def admin_booking_assign(request, booking_id):
    booking = get_object_or_404(RepairBooking, pk=booking_id)
    form = WorkerAssignmentForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Choose an active Repair Worker.')
        return redirect('bookings:admin_list')

    try:
        assign_worker(
            booking_id=booking.pk,
            worker=form.cleaned_data['worker'],
            actor=request.user,
        )
    except BookingTransitionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, 'Repair Worker assigned.')
    return redirect('bookings:admin_list')
