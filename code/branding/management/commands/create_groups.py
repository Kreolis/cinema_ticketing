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
                'change_event', 'view_event',
                'view_location',
                'view_priceclass',
                'add_ticket', 'change_ticket', 'delete_ticket', 'view_ticket',
                'add_ticketchecker', 'change_ticketchecker', 'delete_ticketchecker', 'view_ticketchecker',
                'view_order'
            ]

            for perm in permissions:
                try:
                    permission = Permission.objects.get(codename=perm)
                    ticket_managers_group.permissions.add(permission)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Permission {perm} not found"))

        # create ticket checkers group
        ticket_checkers_group, created = Group.objects.get_or_create(name='Ticket Checkers')
        if created:
            # Assign permissions for viewing tickets and events
            permissions = [
                'view_event',
                'view_location',
                'view_priceclass',
                'view_ticket', 
                'view_ticketmaster',
            ]

            for perm in permissions:
                try:
                    permission = Permission.objects.get(codename=perm)
                    ticket_checkers_group.permissions.add(permission)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Permission {perm} not found"))

        # create accountants group
        accountants_group, created = Group.objects.get_or_create(name='Accountants')
        if created:
            # Assign permissions for viewing orders and events
            permissions = [
                'view_order', 'change_order', 'delete_order', 'add_order',
                'view_event',
                'view_location',
                'view_priceclass', 'change_priceclass', 'delete_priceclass', 'add_priceclass',
                'view_ticket', 
                'view_ticketmaster',
                'view_ticketchecker',
            ]

            for perm in permissions:
                try:
                    permission = Permission.objects.get(codename=perm)
                    accountants_group.permissions.add(permission)
                except Permission.DoesNotExist:
                    self.stdout.write(self.style.ERROR(f"Permission {perm} not found"))

        # create admin group
        admins_group, created = Group.objects.get_or_create(name='Admins')
        if created:
            # Assign all permissions to admins
            all_permissions = Permission.objects.all()
            admins_group.permissions.set(all_permissions)

        self.stdout.write(self.style.SUCCESS('Groups and permissions created successfully'))
