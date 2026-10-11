from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from accounts.roles import REPAIR_WORKER_GROUP, SHOPKEEPER_GROUP


class Command(BaseCommand):
    help = 'Create BENI role groups required for workspace access.'

    def handle(self, *args, **options):
        required_names = (SHOPKEEPER_GROUP, REPAIR_WORKER_GROUP)
        expected_names = {name.casefold() for name in required_names}
        conflicts = sorted(
            name
            for name in Group.objects.values_list('name', flat=True)
            if name.casefold() in expected_names and name not in required_names
        )
        if conflicts:
            raise CommandError(
                'Case-colliding role group(s) exist: '
                f'{", ".join(conflicts)}. Review their memberships before rerunning.'
            )

        for group_name in required_names:
            group, created = Group.objects.get_or_create(name=group_name)
            action = 'Created' if created else 'Already exists'
            self.stdout.write(f'{action}: {group.name}')