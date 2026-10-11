from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from accounts.roles import REPAIR_WORKER_GROUP, SHOPKEEPER_GROUP, user_has_role_group


def group_required(group_name):
	def decorator(view_func):
		@wraps(view_func)
		@login_required(login_url='accounts:login')
		def wrapped_view(request, *args, **kwargs):
			if not user_has_role_group(request.user, group_name):
				raise PermissionDenied
			return view_func(request, *args, **kwargs)

		return wrapped_view

	return decorator


@login_required(login_url='accounts:login')
def customer_dashboard(request):
	if request.user.is_staff or any(
		user_has_role_group(request.user, group_name)
		for group_name in (SHOPKEEPER_GROUP, REPAIR_WORKER_GROUP)
	):
		raise PermissionDenied
	return render(request, 'customer/dashboard.html', {'role_label': 'Customer'})


@group_required(SHOPKEEPER_GROUP)
def shopkeeper_dashboard(request):
	return render(request, 'shopkeeper/dashboard.html', {'role_label': 'Shopkeeper'})


@group_required(REPAIR_WORKER_GROUP)
def repair_worker_dashboard(request):
	return render(request, 'repair_worker/dashboard.html', {'role_label': 'Repair worker'})


@staff_member_required(login_url='accounts:login')
def admin_dashboard(request):
	return render(request, 'admin_panel/dashboard.html', {'role_label': 'Admin'})
