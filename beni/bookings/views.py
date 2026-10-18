from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.roles import REPAIR_WORKER_GROUP, role_group_required
from customers.views import is_customer_user

from .forms import (
    RepairBookingForm,
    WorkerAssignmentForm,
    WorkerBookingStatusForm,
)
from .models import RepairBooking
from .services import (
    BookingTransitionError,
    active_repair_workers,
    assign_worker,
    transition_worker_booking,
)
from verification.services import is_verified_repair_worker


def _customer_only(request):
    if not is_customer_user(request.user):
        raise PermissionDenied


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
    form = RepairBookingForm(
        request.POST if request.method == 'POST' else None,
    )
    if request.method == 'POST' and form.is_valid():
        booking = form.save(commit=False)
        booking.customer = request.user
        booking.save()
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
        RepairBooking.objects.select_related('assigned_worker'),
        pk=booking_id,
        customer=request.user,
    )
    return render(
        request,
        'customer/repairs/detail.html',
        {'booking': booking, 'role_label': 'Customer'},
    )


@role_group_required(REPAIR_WORKER_GROUP)
def worker_booking_list(request):
    if not is_verified_repair_worker(request.user):
        raise PermissionDenied
    bookings = list(
        RepairBooking.objects.filter(assigned_worker=request.user)
    )
    for booking in bookings:
        booking.status_form = WorkerBookingStatusForm(
            current_status=booking.status,
        )
    return render(
        request,
        'repair_worker/repairs/list.html',
        {'bookings': bookings, 'role_label': 'Repair worker'},
    )


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
    )
    if not form.is_valid():
        messages.error(request, 'Choose a permitted next job status.')
        return redirect('bookings:worker_list')

    try:
        changed = transition_worker_booking(
            booking_id=booking.pk,
            worker=request.user,
            new_status=form.cleaned_data['status'],
        )
    except BookingTransitionError as exc:
        messages.error(request, str(exc))
    else:
        if changed is None:
            messages.error(request, 'That assigned job could not be found.')
        else:
            messages.success(request, 'Repair job status updated.')
    return redirect('bookings:worker_list')


@staff_member_required(login_url='accounts:login')
def admin_booking_list(request):
    unassigned_only = request.GET.get('assignment') == 'unassigned'
    booking_queryset = RepairBooking.objects.select_related(
        'customer',
        'assigned_worker',
    )
    if unassigned_only:
        booking_queryset = booking_queryset.filter(assigned_worker__isnull=True)
    bookings = list(booking_queryset)
    for booking in bookings:
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
