from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    role_group_required,
)
from bookings.models import RepairBooking
from customers.views import is_customer_user
from orders.models import Order
from verification.services import is_verified_repair_worker

from .forms import ReviewModerationForm, ReviewSubmissionForm
from .models import Review
from .services import (
    ReviewWorkflowError,
    moderate_review,
    submit_order_review,
    submit_repair_review,
)


def _render_review_submission(
    request,
    *,
    form,
    review_target,
    submit_url,
    submit_arg,
    back_url,
    back_arg,
):
    return render(
        request,
        'reviews/submit.html',
        {
            'form': form,
            'review_target': review_target,
            'submit_url': submit_url,
            'submit_args': (submit_arg,),
            'back_url': back_url,
            'back_args': (back_arg,),
            'role_label': 'Customer',
        },
    )


@login_required(login_url='accounts:login')
def customer_review_list(request):
    if not is_customer_user(request.user):
        raise PermissionDenied
    reviews = Review.objects.filter(customer=request.user).select_related(
        'order',
        'order__shop',
        'booking',
        'booking__assigned_worker',
    )
    return render(
        request,
        'reviews/customer_list.html',
        {'reviews': reviews, 'role_label': 'Customer'},
    )


@require_http_methods(['GET', 'POST'])
@login_required(login_url='accounts:login')
def submit_order_review_view(request, order_number):
    if not is_customer_user(request.user):
        raise PermissionDenied
    order = get_object_or_404(
        Order.objects.select_related('shop'),
        order_number=order_number,
        customer=request.user,
    )
    if order.status != Order.STATUS_DELIVERED:
        messages.error(request, 'An order review is available only after delivery.')
        return redirect('customers:order_detail', order_number=order_number)
    if Review.objects.filter(order=order).exists():
        messages.info(request, 'You have already submitted a review for this order.')
        return redirect('reviews:customer_list')
    if request.method == 'GET':
        return _render_review_submission(
            request,
            form=ReviewSubmissionForm(),
            review_target=order.shop.name,
            submit_url='reviews:submit_order',
            submit_arg=order_number,
            back_url='customers:order_detail',
            back_arg=order_number,
        )
    form = ReviewSubmissionForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Choose a rating and correct the review text.')
        return _render_review_submission(
            request,
            form=form,
            review_target=order.shop.name,
            submit_url='reviews:submit_order',
            submit_arg=order_number,
            back_url='customers:order_detail',
            back_arg=order_number,
        )
    try:
        review = submit_order_review(
            order_number=order_number,
            customer=request.user,
            rating=form.cleaned_data['rating'],
            body=form.cleaned_data['body'],
        )
    except ReviewWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        if review is None:
            raise Http404
        messages.success(
            request,
            'Your review was submitted and is waiting for moderation.',
        )
    return redirect('customers:order_detail', order_number=order_number)


@require_http_methods(['GET', 'POST'])
@login_required(login_url='accounts:login')
def submit_repair_review_view(request, booking_id):
    if not is_customer_user(request.user):
        raise PermissionDenied
    booking = get_object_or_404(
        RepairBooking.objects.select_related('assigned_worker'),
        pk=booking_id,
        customer=request.user,
    )
    if (
        booking.status != RepairBooking.STATUS_COMPLETED
        or booking.assigned_worker_id is None
    ):
        messages.error(
            request,
            'A repair review is available only after a completed assigned repair.',
        )
        return redirect('bookings:customer_detail', booking_id=booking_id)
    if Review.objects.filter(booking=booking).exists():
        messages.info(request, 'You have already submitted a review for this repair.')
        return redirect('reviews:customer_list')
    worker_name = (
        booking.assigned_worker.get_full_name()
        or booking.assigned_worker.get_username()
    )
    if request.method == 'GET':
        return _render_review_submission(
            request,
            form=ReviewSubmissionForm(),
            review_target=worker_name,
            submit_url='reviews:submit_repair',
            submit_arg=booking_id,
            back_url='bookings:customer_detail',
            back_arg=booking_id,
        )
    form = ReviewSubmissionForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Choose a rating and correct the review text.')
        return _render_review_submission(
            request,
            form=form,
            review_target=worker_name,
            submit_url='reviews:submit_repair',
            submit_arg=booking_id,
            back_url='bookings:customer_detail',
            back_arg=booking_id,
        )
    try:
        review = submit_repair_review(
            booking_id=booking_id,
            customer=request.user,
            rating=form.cleaned_data['rating'],
            body=form.cleaned_data['body'],
        )
    except ReviewWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        if review is None:
            raise Http404
        messages.success(
            request,
            'Your repair review was submitted and is waiting for moderation.',
        )
    return redirect('bookings:customer_detail', booking_id=booking_id)


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_review_list(request):
    reviews = Review.objects.filter(
        order__shop__owner=request.user,
        status=Review.STATUS_PUBLISHED,
    ).select_related('customer', 'order', 'order__shop')
    summary = reviews.aggregate(
        average_rating=Avg('rating'),
    )
    return render(
        request,
        'reviews/target_list.html',
        {
            'reviews': reviews,
            'average_rating': summary['average_rating'],
            'review_count': reviews.count(),
            'role_label': 'Shopkeeper',
        },
    )


@role_group_required(REPAIR_WORKER_GROUP)
def worker_review_list(request):
    if not is_verified_repair_worker(request.user):
        raise PermissionDenied
    reviews = Review.objects.filter(
        booking__assigned_worker=request.user,
        status=Review.STATUS_PUBLISHED,
    ).select_related('customer', 'booking')
    summary = reviews.aggregate(
        average_rating=Avg('rating'),
    )
    return render(
        request,
        'reviews/target_list.html',
        {
            'reviews': reviews,
            'average_rating': summary['average_rating'],
            'review_count': reviews.count(),
            'role_label': 'Repair worker',
        },
    )


@staff_member_required(login_url='accounts:login')
def moderation_queue(request):
    reviews = list(
        Review.objects.filter(status=Review.STATUS_PENDING)
        .select_related(
            'customer',
            'order',
            'order__shop',
            'booking',
            'booking__assigned_worker',
        )
    )
    for review in reviews:
        review.moderation_form = ReviewModerationForm(
            prefix=f'review-{review.pk}',
        )
    return render(
        request,
        'reviews/moderation_queue.html',
        {'reviews': reviews, 'role_label': 'Admin'},
    )


@require_POST
@staff_member_required(login_url='accounts:login')
def moderate_review_view(request, review_id):
    form = ReviewModerationForm(request.POST, prefix=f'review-{review_id}')
    if not form.is_valid():
        messages.error(
            request,
            'Choose a moderation decision and provide a reason if declining.',
        )
        return redirect('reviews:moderation_queue')
    try:
        review = moderate_review(
            review_id=review_id,
            moderator=request.user,
            status=form.cleaned_data['status'],
            moderation_note=form.cleaned_data['moderation_note'],
        )
    except ReviewWorkflowError as exc:
        messages.error(request, str(exc))
    else:
        if review is None:
            raise Http404
        messages.success(request, 'Review moderation was recorded.')
    return redirect('reviews:moderation_queue')

# Create your views here.
