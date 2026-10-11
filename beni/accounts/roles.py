from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

SHOPKEEPER_GROUP = 'Shopkeeper'
REPAIR_WORKER_GROUP = 'Repair Worker'


def user_has_role_group(user, group_name):
    return any(
        stored_name == group_name
        for stored_name in user.groups.values_list('name', flat=True)
    )


def role_group_required(group_name):
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url='accounts:login')
        def wrapped_view(request, *args, **kwargs):
            if not user_has_role_group(request.user, group_name):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator