CONTRIBUTOR_GROUP_NAME = 'Repair Guide Contributor'


def can_contribute_guides(user):
    if not user.is_authenticated or not user.is_active:
        return False
    return user.is_staff or user.groups.filter(
        name=CONTRIBUTOR_GROUP_NAME,
    ).exists()


def can_edit_guide(user, guide):
    if not can_contribute_guides(user):
        return False
    if user.is_staff:
        return True
    return (
        guide.author_id == user.pk
        and guide.status in (
            guide.STATUS_DRAFT,
            guide.STATUS_REJECTED,
        )
    )
