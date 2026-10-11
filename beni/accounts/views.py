from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.urls import reverse

from .forms import RegistrationForm


def role_dashboard_url(user):
	if user.is_staff:
		return reverse('dashboard:admin')
	if user.groups.filter(name='Shopkeeper').exists():
		return reverse('dashboard:shopkeeper')
	if user.groups.filter(name='Repair Worker').exists():
		return reverse('dashboard:repair_worker')
	return reverse('dashboard:customer')


def register(request):
	if request.user.is_authenticated:
		return redirect(role_dashboard_url(request.user))

	form = RegistrationForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		login(request, user)
		return redirect(role_dashboard_url(user))

	return render(request, 'auth/register.html', {'form': form})
