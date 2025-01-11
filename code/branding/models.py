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
    firstname = models.CharField(max_length=100)
    lastname = models.CharField(max_length=100)
    email = models.EmailField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.firstname} {self.lastname}"
    

# model for logos and other branding images
class Branding(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='branding/images', null=True, blank=True)
    favicon = models.ImageField(upload_to='branding/images', null=True, blank=True)
    success_sound = models.FileField(upload_to='branding/sounds', null=True, blank=True)
    is_active = models.BooleanField(default=False)

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
