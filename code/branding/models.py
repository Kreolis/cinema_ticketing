from django.db import models
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image

# model for contact form emails
class Contact(models.Model):
    firstname = models.CharField(max_length=100, help_text=_("Enter the first name"))
    lastname = models.CharField(max_length=100, help_text=_("Enter the last name"))
    email = models.EmailField(help_text=_("Enter the email address"))
    is_active = models.BooleanField(default=False, help_text=_("Indicates if the contact is active"))

    def __str__(self):
        return f"{self.firstname} {self.lastname}"
    

# model for logos and other branding images
class Branding(models.Model):
    name = models.CharField(max_length=100, help_text=_("Enter the name of your branding"))
    site_name = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter the name of your site. This will be used as the title of the site and in communcations."))
    logo = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the logo image"))
    favicon = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the favicon image (max 64x64 pixels)"))
    order_timeout = models.IntegerField(default=10, help_text=_("Timeout in minutes until user needs to start fresh with their order"))
    success_sound = models.FileField(upload_to='branding/sounds', null=True, blank=True, help_text=_("Upload the success sound file for ticket scanner"))

    # general event and ticket settings
    ticket_background = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the global ticket background image"))
    event_background = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the global event background image"))
    allow_presale = models.BooleanField(default=True, help_text=_("Indicates if presale is allowed"))
    presale_ends_before = models.IntegerField(default=1, help_text=_("Number of hours before event start when presale ends and door (not presale) selling starts"))
    allow_door_selling = models.BooleanField(default=True, help_text=_("Indicates if selling tickets at the door is allowed"))

    # invoice settings
    invoice_background = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the global invoice background image"))
    invoice_logo = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the logo image for invoices"))
    invoice_company_name = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter your name to appear on invoices"))
    invoice_address_1 = models.TextField(null=True, blank=True, help_text=_("Enter your address to appear on invoices"))
    invoice_address_2 = models.TextField(null=True, blank=True, help_text=_("Enter your address to appear on invoices"))
    invoice_city = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter your city to appear on invoices"))
    invoice_postal_code = models.CharField(max_length=20, null=True, blank=True, help_text=_("Enter your postal code to appear on invoices"))
    invoice_country = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter your country to appear on invoices"))
    invoice_email = models.EmailField(null=True, blank=True, help_text=_("Enter your email address to appear on invoices"))
    invoice_phone = models.CharField(max_length=20, null=True, blank=True, help_text=_("Enter your phone number to appear on invoices"))
    invoice_vat_id = models.CharField(max_length=20, null=True, blank=True, help_text=_("Enter your VAT number to appear on invoices"))
    invoice_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text=_("Enter the tax rate to appear on invoices"))

    is_active = models.BooleanField(default=False, help_text=_("Indicates if this branding is active"))

    def __str__(self):
        return self.name
    
    # make sure only one image is active at a time
    def save(self, *args, **kwargs):
        if self.is_active:
            Branding.objects.filter(is_active=True).update(is_active=False)
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
                raise ValidationError(_("Favicon size should not exceed 64x64 pixels."))


def get_active_branding():
    from django.db import connection
    if 'branding_branding' in connection.introspection.table_names():
        if Branding.objects.filter(is_active=True).exists():
            return Branding.objects.filter(is_active=True).first()
    return None
