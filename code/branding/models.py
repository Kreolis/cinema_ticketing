from django.db import models
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from PIL import Image

# create ticket managers group
ticket_managers_group, created = Group.objects.get_or_create(name='Ticket Managers')
if created:
    # Assign permissions ticket and events management
    permissions = [
        'add_event', 'add_location', 'add_priceclass', 'add_ticket',
        'change_event', 'change_location', 'change_priceclass', 'change_ticket',
        'delete_event', 'delete_location', 'delete_priceclass', 'delete_ticket',
        'view_event', 'view_location', 'view_priceclass', 'view_ticket',
        'add_payment', 'change_payment', 'delete_payment', 'view_payment'
    ]

    for perm in permissions:
        permission = Permission.objects.get(codename=perm)
        ticket_managers_group.permissions.add(permission)


# create admin group
admins_group, created = Group.objects.get_or_create(name='Admins')
if created:
    # Assign all permissions to admins
    all_permissions = Permission.objects.all()
    admins_group.permissions.set(all_permissions)
    

# model for contact form emails
class Contact(models.Model):
    firstname = models.CharField(max_length=100, help_text="Enter the first name")
    lastname = models.CharField(max_length=100, help_text="Enter the last name")
    email = models.EmailField(help_text="Enter the email address")
    is_active = models.BooleanField(default=False, help_text="Indicates if the contact is active")

    def __str__(self):
        return f"{self.firstname} {self.lastname}"
    

# model for logos and other branding images
class Branding(models.Model):
    name = models.CharField(max_length=100, help_text="Enter the name of your branding")
    logo = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text="Upload the logo image")
    favicon = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text="Upload the favicon image (max 64x64 pixels)")
    ticket_background = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text="Upload the global ticket background image")
    event_background = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text="Upload the global event background image")
    order_timeout = models.IntegerField(default=10, help_text="Timeout in minutes until user needs to start fresh with their order")
    success_sound = models.FileField(upload_to='branding/sounds', null=True, blank=True, help_text="Upload the success sound file for ticket scanner")
    is_active = models.BooleanField(default=False, help_text="Indicates if this branding is active")

    def __str__(self):
        return self.name
    
    # make sure only one image is active at a time
    def save(self, *args, **kwargs):
        if self.is_active:
            Branding.objects.all().update(is_active=False)
        super(Branding, self).save(*args, **kwargs)

    # delete image files when object is deleted
    def delete(self, *args, **kwargs):
        self.logo.delete()
        self.favicon.delete()
        self.success_sound.delete()
        super(Branding, self).delete(*args, **kwargs)

    def clean(self):
        if self.favicon:
            image = Image.open(self.favicon)
            if image.width > 64 or image.height > 64:
                raise ValidationError("Favicon size should not exceed 64x64 pixels.")


def get_active_branding():
    if Branding.objects.filter(is_active=True).exists():
        return Branding.objects.filter(is_active=True).first()
    else:
        return None
