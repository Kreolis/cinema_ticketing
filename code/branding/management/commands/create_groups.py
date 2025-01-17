from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission

class Command(BaseCommand):
    help = 'Create groups and assign permissions'

    def handle(self, *args, **kwargs):
        # create ticket managers group
        ticket_managers_group, created = Group.objects.get_or_create(name='Ticket Managers')
        if created:
            # Assign permissions ticket and events management
            permissions = [
                'add_event', 'change_event', 'delete_event', 'view_event',
                'add_location', 'change_location', 'delete_location', 'view_location',
                'add_priceclass', 'change_priceclass', 'delete_priceclass', 'view_priceclass',
                'add_ticket', 'change_ticket', 'delete_ticket', 'view_ticket',
                'add_order', 'change_order', 'delete_order', 'view_order'
            ]

            for perm in permissions:
                try:
                    permission = Permission.objects.get(codename=perm)
                    ticket_managers_group.permissions.add(permission)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Permission {perm} not found"))

        # create admin group
        admins_group, created = Group.objects.get_or_create(name='Admins')
        if created:
            # Assign all permissions to admins
            all_permissions = Permission.objects.all()
            admins_group.permissions.set(all_permissions)

        self.stdout.write(self.style.SUCCESS('Groups and permissions created successfully'))
