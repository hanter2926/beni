from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import (
    REPAIR_WORKER_GROUP,
    SHOPKEEPER_GROUP,
    user_has_role_group,
)
from .models import Notification


def _notification_role_label(user):
    if user.is_staff:
        return 'Admin'
    if user_has_role_group(user, SHOPKEEPER_GROUP):
        return 'Shopkeeper'
    if user_has_role_group(user, REPAIR_WORKER_GROUP):
        return 'Repair worker'
    return 'Customer'


@login_required(login_url='accounts:login')
def inbox(request):
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).order_by('-created_at', '-pk')
    page_obj = Paginator(notifications, 25).get_page(request.GET.get('page'))
    return render(
        request,
        'notifications/inbox.html',
        {
            'page_obj': page_obj,
            'role_label': _notification_role_label(request.user),
            'active_nav': 'notifications',
        },
    )


@require_POST
@login_required(login_url='accounts:login')
def mark_read(request, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )
    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=('read_at',))
    return redirect('notifications:inbox')


@require_POST
@login_required(login_url='accounts:login')
def mark_all_read(request):
    Notification.objects.filter(
        recipient=request.user,
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    return redirect('notifications:inbox')
