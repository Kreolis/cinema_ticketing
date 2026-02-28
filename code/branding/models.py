from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from PIL import Image

import logging

logger = logging.getLogger(__name__)

from cinema_tickets.celery import app

# model for contact form emails
class Contact(models.Model):
    firstname = models.CharField(max_length=100, help_text=_("Enter the first name"))
    lastname = models.CharField(max_length=100, help_text=_("Enter the last name"))
    email = models.EmailField(help_text=_("Enter the email address to which the contact form is sent"))
    is_active = models.BooleanField(default=False, help_text=_("Indicates if the contact is active"))

    def __str__(self):
        return f"{self.firstname} {self.lastname}"

# model for logos and other branding images
class Branding(models.Model):
    name = models.CharField(max_length=100, help_text=_("Enter the name of your branding"))
    site_name = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter the name of your site. This will be used as the title of the site and in communications."))
    site_url = models.URLField(null=True, blank=True, help_text=_("Enter the URL of your site. This will be used in communications."))
    logo = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the logo image"))
    favicon = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the favicon image (max 64x64 pixels)"))
    order_timeout = models.IntegerField(default=10, help_text=_("Timeout in minutes until user needs to start fresh with their order"))
    success_sound = models.FileField(upload_to='branding/sounds', null=True, blank=True, help_text=_("Upload the success sound file for ticket scanner"))

    # general event and ticket settings
    ticket_background = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the global ticket background image"))
    display_seat_number = models.BooleanField(default=False, help_text=_("Indicates if seat numbers are displayed for customers, if not free seating text is displayed"))
    event_background = models.ImageField(upload_to='branding/images', null=True, blank=True, help_text=_("Upload the global event background image"))
    allow_presale = models.BooleanField(default=True, help_text=_("Indicates if presale is allowed"))
    presale_start = models.DateTimeField(null=True, blank=True, help_text=_("Enter the date and time when presale starts"))
    presale_ends_before = models.IntegerField(default=1, help_text=_("Number of hours before event start when presale ends and door (not presale) selling starts"))
    allow_door_selling = models.BooleanField(default=True, help_text=_("Indicates if selling tickets at the door is allowed"))
    check_timeout_orders_interval = models.IntegerField(default=30, help_text=_("Interval in minutes for checking timed out orders"))

    # ticket statistics settings
    enable_ticket_statistics_sending = models.BooleanField(default=False, help_text=_("Indicates if ticket statistics are sent via email"))
    ticket_statistics_email = models.EmailField(null=True, blank=True, help_text=_("Enter the email address to receive ticket statistics"))
    ticket_statistics_interval = models.IntegerField(default=24, help_text=_("Enter the interval in hours for sending ticket statistics"))
    ticket_statistics_start = models.DateTimeField(default=None, null=True, blank=True, help_text=_("Enter the date and time when ticket statistics should start sending"))
    ticket_statistics_end = models.DateTimeField(default=None, null=True, blank=True, help_text=_("Enter the date and time when ticket statistics should stop sending"))

    # invoice settings
    display_invoice_info = models.BooleanField(default=True, help_text=_("Indicates if invoice information is displayed on auto generated invoices"))
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
    invoice_tax_rate = models.DecimalField(max_digits=3, decimal_places=2, default=0, help_text=_("Enter the tax rate in percent to appear on invoices"))
    
    invoice_padding_top = models.IntegerField(default=1, help_text=_("Enter the padding in cm for the top of the invoice"))
    invoice_padding_left = models.IntegerField(default=1, help_text=_("Enter the padding in cm for the left of the invoice"))
    invoice_padding_right = models.IntegerField(default=1, help_text=_("Enter the padding in cm for the right of the invoice"))
    invoice_padding_bottom = models.IntegerField(default=1, help_text=_("Enter the padding in cm for the bottom of the invoice"))
    
    advanced_payment_bank_account_name = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter the bank account name for advanced payments"))
    advanced_payment_bank_name = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter the bank name for advanced payments"))
    advanced_payment_iban = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter the IBAN for advanced payments"))
    advanced_payment_swift = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter the SWIFT code for advanced payments"))
    advanced_payment_reference = models.CharField(max_length=100, null=True, blank=True, help_text=_("Enter the reference for advanced payments. This is also used as invoice number."))
    advanced_payment_due_days = models.IntegerField(default=14, help_text=_("Enter the number of days until payment is due for advanced payments"))
    advanced_payment_message = models.TextField(default="Please transfer the total amount to the following bank account.", null=True, blank=True, help_text=_("Enter the message to appear on advanced payment emails"))

    is_active = models.BooleanField(default=False, help_text=_("Indicates if this branding is active"))

    def __str__(self):
        return self.name
    
    # make sure only one branding is active at a time
    def save(self, *args, **kwargs):
        if self.is_active:
            Branding.objects.filter(is_active=True).update(is_active=False)

        update_statistics_task_schedule(instance=self)  # update the statistics task schedule whenever
        super(Branding, self).save(*args, **kwargs)

    # delete image files when object is deleted
    def delete(self, *args, **kwargs):
        self.logo.delete()
        self.favicon.delete()
        self.success_sound.delete()
        update_statistics_task_schedule(instance=self) # update the statistics task schedule
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


def update_statistics_task_schedule(instance):
    logger.info("Branding saved, updating statistics task schedule if needed.")
    # check if statistics sending is enabled and update the Celery beat schedule accordingly
    if instance.enable_ticket_statistics_sending:
        # make sure if task already exists in beat schedule, if so remove it before adding the updated one
        if 'send_global_statistics_report_task-every-X-hours' in app.conf.beat_schedule:
            del app.conf.beat_schedule['send_global_statistics_report_task-every-X-hours']

        # check if sedning period has started and has not ended yet before scheduling the task
        now = timezone.now()
        if instance.ticket_statistics_start and now < instance.ticket_statistics_start:
            return  # Do not schedule the task if the start date is in the future
        if instance.ticket_statistics_end and now > instance.ticket_statistics_end:
            return  # Do not schedule the task if the end date has passed
        
        app.conf.beat_schedule.update({
            'send_global_statistics_report_task-every-X-hours': {
                'task': 'events.tasks.send_global_statistics_report_task',
                'schedule': instance.ticket_statistics_interval * 3600.0,  # convert hours to seconds
            },
        })
    else:
        if 'send_global_statistics_report_task-every-X-hours' in app.conf.beat_schedule:
            del app.conf.beat_schedule['send_global_statistics_report_task-every-X-hours']