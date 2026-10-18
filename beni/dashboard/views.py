from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.core.paginator import Paginator
from django.shortcuts import render

from accounts.roles import (
	REPAIR_WORKER_GROUP,
	SHOPKEEPER_GROUP,
	role_group_required,
	user_has_role_group,
)
from bookings.models import RepairBooking
from orders.models import Order
from products.models import Product
from shops.models import Shop
from verification.models import VerificationApplication


@login_required(login_url='accounts:login')
def customer_dashboard(request):
	if request.user.is_staff or any(
		user_has_role_group(request.user, group_name)
		for group_name in (SHOPKEEPER_GROUP, REPAIR_WORKER_GROUP)
	):
		raise PermissionDenied
	return render(request, 'customer/dashboard.html', {'role_label': 'Customer'})


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_dashboard(request):
	return render(request, 'shopkeeper/dashboard.html', {'role_label': 'Shopkeeper'})


@role_group_required(REPAIR_WORKER_GROUP)
def repair_worker_dashboard(request):
	return render(request, 'repair_worker/dashboard.html', {'role_label': 'Repair worker'})


@staff_member_required(login_url='accounts:login')
def admin_dashboard(request):
	status_counts = {
		row['status']: row['total']
		for row in Order.objects.values('status').annotate(total=Count('pk'))
	}
	payment_status_counts = {
		row['payment_status']: row['total']
		for row in Order.objects.values('payment_status').annotate(total=Count('pk'))
	}
	booking_status_counts = {
		row['status']: row['total']
		for row in RepairBooking.objects.values('status').annotate(total=Count('pk'))
	}
	marketplace_users = get_user_model().objects.filter(
		is_staff=False,
		is_superuser=False,
	)
	in_fulfilment_statuses = (
		Order.STATUS_CONFIRMED,
		Order.STATUS_PROCESSING,
		Order.STATUS_READY_FOR_PICKUP,
		Order.STATUS_OUT_FOR_DELIVERY,
	)
	context = {
		'role_label': 'Admin',
		'orders_total': sum(status_counts.values()),
		'orders_pending': status_counts.get(Order.STATUS_PENDING, 0),
		'orders_in_fulfilment': sum(
			status_counts.get(status, 0) for status in in_fulfilment_statuses
		),
		'orders_delivered': status_counts.get(Order.STATUS_DELIVERED, 0),
		'orders_cancelled': status_counts.get(Order.STATUS_CANCELLED, 0),
		'orders_refunded': status_counts.get(Order.STATUS_REFUNDED, 0),
		'payments_not_started': payment_status_counts.get(
			Order.PAYMENT_NOT_STARTED, 0
		),
		'payments_pending': payment_status_counts.get(Order.PAYMENT_PENDING, 0),
		'payments_failed': payment_status_counts.get(Order.PAYMENT_FAILED, 0),
		'payments_paid': payment_status_counts.get(Order.PAYMENT_PAID, 0),
		'payments_refunded': payment_status_counts.get(
			Order.PAYMENT_REFUNDED, 0
		),
		'active_shops': Shop.objects.filter(is_active=True).count(),
		'inactive_shops': Shop.objects.filter(is_active=False).count(),
		'shops_pending_verification': VerificationApplication.objects.filter(
			application_type=VerificationApplication.TYPE_SHOPKEEPER,
			status=VerificationApplication.STATUS_PENDING,
		).count(),
		'active_products': Product.objects.filter(
			is_active=True,
			shop__is_active=True,
		).count(),
		'bookings_total': sum(booking_status_counts.values()),
		'bookings_unassigned': RepairBooking.objects.filter(
			assigned_worker__isnull=True
		).count(),
		'bookings_requested': booking_status_counts.get(
			RepairBooking.STATUS_REQUESTED, 0
		),
		'customers_total': marketplace_users.exclude(
			groups__name__in=(SHOPKEEPER_GROUP, REPAIR_WORKER_GROUP)
		).distinct().count(),
		'shopkeepers_total': marketplace_users.filter(
			groups__name=SHOPKEEPER_GROUP
		).distinct().count(),
		'repair_workers_total': marketplace_users.filter(
			groups__name=REPAIR_WORKER_GROUP
		).distinct().count(),
	}
	return render(request, 'admin_panel/dashboard.html', context)


@staff_member_required(login_url='accounts:login')
def admin_user_list(request):
	user_model = get_user_model()
	users = user_model.objects.filter(
		is_staff=False,
		is_superuser=False,
	).prefetch_related('groups', 'verification_applications')

	role = request.GET.get('role', '')
	if role == 'shopkeeper':
		users = users.filter(groups__name=SHOPKEEPER_GROUP)
	elif role == 'repair_worker':
		users = users.filter(groups__name=REPAIR_WORKER_GROUP)
	elif role == 'customer':
		users = users.exclude(
			groups__name__in=(SHOPKEEPER_GROUP, REPAIR_WORKER_GROUP)
		)
	else:
		role = ''

	account_status = request.GET.get('status', '')
	if account_status == 'active':
		users = users.filter(is_active=True)
	elif account_status == 'inactive':
		users = users.filter(is_active=False)
	else:
		account_status = ''

	query = request.GET.get('q', '').strip()
	if query:
		users = users.filter(username__icontains=query)

	users = users.distinct().order_by('username', 'pk')
	page_obj = Paginator(users, 50).get_page(request.GET.get('page'))
	for user in page_obj.object_list:
		group_names = {group.name for group in user.groups.all()}
		user.marketplace_roles = []
		if SHOPKEEPER_GROUP in group_names:
			user.marketplace_roles.append('Shopkeeper')
		if REPAIR_WORKER_GROUP in group_names:
			user.marketplace_roles.append('Repair Worker')
		if not user.marketplace_roles:
			user.marketplace_roles.append('Customer')
		user.verification_summary = [
			(
				application.get_application_type_display(),
				application.get_status_display(),
			)
			for application in user.verification_applications.all()
		]

	return render(
		request,
		'admin_panel/users.html',
		{
			'page_obj': page_obj,
			'query': query,
			'selected_role': role,
			'account_status': account_status,
			'role_label': 'Admin',
		},
	)
