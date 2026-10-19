from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from beni.private_files import private_image_response

from .models import Profile
from .forms import ProfileForm, RegistrationForm
from .roles import REPAIR_WORKER_GROUP, SHOPKEEPER_GROUP, user_has_role_group


def role_dashboard_url(user):
	if user.is_staff:
		return reverse('dashboard:admin')
	if user_has_role_group(user, SHOPKEEPER_GROUP):
		return reverse('dashboard:shopkeeper')
	if user_has_role_group(user, REPAIR_WORKER_GROUP):
		return reverse('dashboard:repair_worker')
	return reverse('dashboard:customer')


def register(request):
	if request.user.is_authenticated:
		return redirect(role_dashboard_url(request.user))

	form = RegistrationForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		with transaction.atomic():
			user = form.save()
			role_group = {
				RegistrationForm.ROLE_SHOPKEEPER: SHOPKEEPER_GROUP,
				RegistrationForm.ROLE_REPAIR_WORKER: REPAIR_WORKER_GROUP,
			}.get(form.cleaned_data['role'])
			if role_group:
				group, _ = Group.objects.get_or_create(name=role_group)
				user.groups.add(group)
		login(request, user)
		return redirect(role_dashboard_url(user))

	return render(request, 'auth/register.html', {'form': form})


@login_required(login_url='accounts:login')
def profile(request):
	form_data = request.POST if request.method == 'POST' else None
	files_data = request.FILES if request.method == 'POST' else None
	profile_record = Profile.objects.filter(user=request.user).first()
	form = ProfileForm(
		form_data,
		files_data,
		instance=request.user,
		profile=profile_record,
	)
	if request.method == 'POST' and form.is_valid():
		form.save()
		messages.success(request, 'Your profile was updated.')
		return redirect('accounts:profile')

	return render(
		request,
		'auth/profile.html',
		{
			'form': form,
			'profile': profile_record,
			'role_label': 'Account',
			'dashboard_url': role_dashboard_url(request.user),
		},
	)


@login_required(login_url='accounts:login')
def private_profile_image(request, user_id):
	authorized = request.user.pk == user_id or request.user.is_staff
	if not authorized:
		from bookings.models import RepairBooking

		authorized = RepairBooking.objects.filter(
			customer_id=request.user.pk,
			assigned_worker_id=user_id,
			status__in=RepairBooking.CONTACT_ALLOWED_STATUSES,
		).exists()
	if not authorized:
		raise Http404
	profile_record = get_object_or_404(
		Profile.objects.select_related('user'),
		user_id=user_id,
	)
	if not profile_record.image:
		raise Http404
	return private_image_response(profile_record.image)
