from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from accounts.models import Profile
from accounts.roles import (
	REPAIR_WORKER_GROUP,
	SHOPKEEPER_GROUP,
	role_group_required,
	user_has_role_group,
)
from bookings.forms import RepairBookingForm
from bookings.models import RepairBooking
from orders.models import Order
from products.models import Product
from products.services import eligible_shop_verifications, marketable_products
from shops.models import Shop
from verification.models import VerificationApplication


REPAIR_CATEGORIES = (
	{
		'name': 'Mobile repair',
		'keywords': ('mobile', 'phone', 'smartphone'),
		'description': 'Screen, battery, charging, and other mobile device problems.',
	},
	{
		'name': 'Laptop repair',
		'keywords': ('laptop', 'notebook', 'computer'),
		'description': 'Hardware, performance, display, and software troubleshooting.',
	},
	{
		'name': 'Electronics repair',
		'keywords': ('electronics', 'electronic', 'tv', 'television'),
		'description': 'Help with household electronics and electronic devices.',
	},
	{
		'name': 'Other repairs',
		'keywords': ('appliance', 'repair', 'service'),
		'description': 'Describe your issue and BENI will route it to a suitable worker.',
	},
)


@login_required(login_url='accounts:login')
def customer_dashboard(request):
	if request.user.is_staff or any(
		user_has_role_group(request.user, group_name)
		for group_name in (SHOPKEEPER_GROUP, REPAIR_WORKER_GROUP)
	):
		raise PermissionDenied

	query = request.GET.get('q', '').strip()[:100]
	selected_category = request.GET.get('category', '').strip()[:100]
	shop_products = marketable_products().select_related('shop')
	if query:
		shop_products = shop_products.filter(
			Q(name__icontains=query)
			| Q(description__icontains=query)
			| Q(category__icontains=query)
			| Q(shop__name__icontains=query)
		)
	if selected_category:
		shop_products = shop_products.filter(category__iexact=selected_category)
	products = list(shop_products[:8])
	categories = (
		marketable_products()
		.order_by('category')
		.values_list('category', flat=True)
		.distinct()
	)

	worker_profiles = list(
		Profile.objects.filter(
			user__is_active=True,
			user__groups__name=REPAIR_WORKER_GROUP,
			user__verification_applications__application_type=(
				VerificationApplication.TYPE_REPAIR_WORKER
			),
			user__verification_applications__status=(
				VerificationApplication.STATUS_APPROVED
			),
			user__verification_applications__phone_status=(
				VerificationApplication.CHECK_VERIFIED
			),
			user__verification_applications__face_status=(
				VerificationApplication.CHECK_VERIFIED
			),
			phone_verified=True,
		).select_related('user').distinct()[:100]
	)
	repair_services = []
	for category in REPAIR_CATEGORIES:
		keywords = category['keywords']
		providers = [
			profile.user.get_full_name() or profile.user.get_username()
			for profile in worker_profiles
			if any(
				keyword in profile.service_details.casefold()
				for keyword in keywords
			)
		][:2]
		repair_services.append({
			**category,
			'providers': providers,
			'estimated_price': 'Quote after inspection',
		})

	orders = list(
		Order.objects.filter(customer=request.user)
		.select_related('shop')
		.prefetch_related('items__product')
		.order_by('-created_at', '-pk')[:5]
	)
	for order in orders:
		order.can_cancel = order.status in (
			Order.STATUS_PENDING,
			Order.STATUS_CONFIRMED,
		)

	selected_tab = request.GET.get('tab', 'shops')
	if selected_tab not in {'shops', 'repair', 'orders'}:
		selected_tab = 'shops'
	booking_form = RepairBookingForm(
		initial={
			'service_category': request.GET.get('service_category', '')[:100],
		}
	)
	return render(
		request,
		'customer/dashboard.html',
		{
			'role_label': 'Customer',
			'products': products,
			'product_count': shop_products.count(),
			'categories': categories,
			'query': query,
			'selected_category': selected_category,
			'repair_services': repair_services,
			'booking_form': booking_form,
			'orders': orders,
			'order_count': Order.objects.filter(customer=request.user).count(),
			'selected_tab': selected_tab,
			'customer_profile': Profile.objects.filter(user=request.user).first(),
		},
	)


@role_group_required(SHOPKEEPER_GROUP)
def shopkeeper_dashboard(request):
	shops = list(
		Shop.objects.filter(owner=request.user)
		.annotate(
			product_count=Count('products'),
			active_product_count=Count(
				'products',
				filter=Q(products__is_active=True),
			),
		)
		.select_related('verification_applications')
	)
	for shop in shops:
		try:
			shop.verification_application = shop.verification_applications
		except VerificationApplication.DoesNotExist:
			shop.verification_application = None
	owned_shop_ids = tuple(shop.pk for shop in shops)
	eligible_shop_ids = set(
		eligible_shop_verifications(
			shop_ids=owned_shop_ids,
		).values_list('shop_id', flat=True)
	)
	for shop in shops:
		shop.marketable = shop.is_active and shop.pk in eligible_shop_ids

	product_counts = Product.objects.filter(
		shop__owner=request.user,
	).aggregate(
		total=Count('pk'),
		active=Count('pk', filter=Q(is_active=True)),
	)
	orders = Order.objects.filter(shop__owner=request.user)
	order_counts = orders.aggregate(
		total=Count('pk'),
		open=Count(
			'pk',
			filter=Q(
				status__in=(
					Order.STATUS_PENDING,
					Order.STATUS_CONFIRMED,
					Order.STATUS_PROCESSING,
					Order.STATUS_READY_FOR_PICKUP,
					Order.STATUS_OUT_FOR_DELIVERY,
				)
			),
		),
	)
	return render(
		request,
		'shopkeeper/dashboard.html',
		{
			'role_label': 'Shopkeeper',
			'shopkeeper_name': (
				request.user.get_full_name() or request.user.get_username()
			),
			'shops': shops,
			'shop_count': len(shops),
			'active_shop_count': sum(shop.marketable for shop in shops),
			'product_count': product_counts['total'],
			'active_product_count': product_counts['active'],
			'inactive_product_count': (
				product_counts['total'] - product_counts['active']
			),
			'order_count': order_counts['total'],
			'open_order_count': order_counts['open'],
			'recent_orders': orders.select_related('shop')[:5],
		},
	)


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
