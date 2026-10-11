from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.roles import (
	REPAIR_WORKER_GROUP,
	SHOPKEEPER_GROUP,
	role_group_required,
	user_has_role_group,
)


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
	return render(request, 'admin_panel/dashboard.html', {'role_label': 'Admin'})
