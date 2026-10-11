SHOPKEEPER_GROUP = 'Shopkeeper'
REPAIR_WORKER_GROUP = 'Repair Worker'


def user_has_role_group(user, group_name):
    return any(
        stored_name == group_name
        for stored_name in user.groups.values_list('name', flat=True)
    )