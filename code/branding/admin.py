from django.contrib import admin
from .models import Contact, TicketMaster, Branding

from django.urls import reverse
from django.utils.html import format_html
import csv
from django.shortcuts import redirect, render
from django.urls import path
from django import forms
from django.http import HttpResponse
from datetime import datetime, timedelta
from django.utils import timezone

import logging

logger = logging.getLogger(__name__)

class CSVImportForm(forms.Form):
    csv_file = forms.FileField(label='CSV file')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('firstname', 'lastname', 'email', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'email')

    def has_view_permission(self, request):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if request.user.groups.filter(name='admin').exists() or request.user.groups.filter(name='ticketmanagers').exists():
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

@admin.register(TicketMaster)
class TicketMasterAdmin(admin.ModelAdmin):
    list_display = ('firstname', 'lastname', 'email', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'email')

    def has_view_permission(self, request):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if request.user.groups.filter(name='admin').exists() or request.user.groups.filter(name='ticketmanagers').exists():
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False
@admin.register(Branding)
class BrandingAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    change_list_template = "admin_brandings_custom.html"

    def has_view_permission(self, request):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if request.user.groups.filter(name='admin').exists() or request.user.groups.filter(name='ticketmanagers').exists():
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv, name='import_branding_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_branding_template_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            try:
                reader = csv.reader(csv_file.read().decode('utf-8').splitlines())
                headers = next(reader)
                for row in reader:
                    branding_data = dict(zip(headers, row))
                    
                    # Parse datetime fields
                    time_format = '%Y-%m-%d %H:%M:%S'
                    presale_start = timezone.make_aware(datetime.strptime(branding_data["presale_start"], time_format)) if branding_data.get("presale_start") else None
                    ticket_statistics_start = timezone.make_aware(datetime.strptime(branding_data["ticket_statistics_start"], time_format)) if branding_data.get("ticket_statistics_start") else None
                    ticket_statistics_end = timezone.make_aware(datetime.strptime(branding_data["ticket_statistics_end"], time_format)) if branding_data.get("ticket_statistics_end") else None
                    
                    branding = Branding.objects.create(
                        name=branding_data["name"],
                        site_name=branding_data.get("site_name", ""),
                        site_url=branding_data.get("site_url", ""),
                        logo=branding_data.get("logo", ""),
                        favicon=branding_data.get("favicon", ""),
                        order_timeout=int(branding_data.get("order_timeout", 15)),
                        success_sound=branding_data.get("success_sound", ""),
                        ticket_background=branding_data.get("ticket_background", ""),
                        display_seat_number=branding_data.get("display_seat_number", "").upper() == 'TRUE',
                        event_background=branding_data.get("event_background", ""),
                        allow_presale=branding_data.get("allow_presale", "").upper() == 'TRUE',
                        presale_start=presale_start,
                        presale_ends_before=int(branding_data.get("presale_ends_before", 1)),
                        allow_door_selling=branding_data.get("allow_door_selling", "").upper() == 'TRUE',
                        check_timeout_orders_interval=int(branding_data.get("check_timeout_orders_interval", 60)),
                        enable_ticket_statistics_sending=branding_data.get("enable_ticket_statistics_sending", "").upper() == 'TRUE',
                        ticket_statistics_email=branding_data.get("ticket_statistics_email", ""),
                        ticket_statistics_interval=int(branding_data.get("ticket_statistics_interval", 24)),
                        ticket_statistics_start=ticket_statistics_start,
                        ticket_statistics_end=ticket_statistics_end,
                        display_invoice_info=branding_data.get("display_invoice_info", "").upper() == 'TRUE',
                        invoice_background=branding_data.get("invoice_background", ""),
                        invoice_logo=branding_data.get("invoice_logo", ""),
                        invoice_company_name=branding_data.get("invoice_company_name", ""),
                        invoice_address_1=branding_data.get("invoice_address_1", ""),
                        invoice_address_2=branding_data.get("invoice_address_2", ""),
                        invoice_city=branding_data.get("invoice_city", ""),
                        invoice_postal_code=branding_data.get("invoice_postal_code", ""),
                        invoice_country=branding_data.get("invoice_country", ""),
                        invoice_email=branding_data.get("invoice_email", ""),
                        invoice_phone=branding_data.get("invoice_phone", ""),
                        invoice_vat_id=branding_data.get("invoice_vat_id", ""),
                        invoice_tax_rate=float(branding_data.get("invoice_tax_rate", 0)),
                        invoice_padding_top=int(branding_data.get("invoice_padding_top", 0)),
                        invoice_padding_left=int(branding_data.get("invoice_padding_left", 0)),
                        invoice_padding_right=int(branding_data.get("invoice_padding_right", 0)),
                        invoice_padding_bottom=int(branding_data.get("invoice_padding_bottom", 0)),
                        advanced_payment_bank_account_name=branding_data.get("advanced_payment_bank_account_name", ""),
                        advanced_payment_bank_name=branding_data.get("advanced_payment_bank_name", ""),
                        advanced_payment_iban=branding_data.get("advanced_payment_iban", ""),
                        advanced_payment_swift=branding_data.get("advanced_payment_swift", ""),
                        advanced_payment_reference=branding_data.get("advanced_payment_reference", ""),
                        advanced_payment_due_days=int(branding_data.get("advanced_payment_due_days", 7)),
                        advanced_payment_message=branding_data.get("advanced_payment_message", ""),
                        is_active=branding_data.get("is_active", "").upper() == 'TRUE',
                    )
                    logger.info(f"Created branding: {branding}")

                self.message_user(request, "Branding imported successfully.")
                return redirect("..")
            except Exception as e:
                error_message = f"Error importing CSV file: {str(e)}"
                form = CSVImportForm()
                payload = {"form": form, "error_message": error_message}
                logger.error(error_message)
                return render(request, "branding_import_csv_form.html", payload)
            
        form = CSVImportForm()
        payload = {"form": form}
        return render(request, "branding_import_csv_form.html", payload)

    def download_template_csv(self, request):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="branding_import_template.csv"'},
        )
        writer = csv.writer(response)
        writer.writerow([
            'name', 'site_name', 'site_url', 'logo', 'favicon', 'order_timeout', 'success_sound', 
            'ticket_background', 'display_seat_number', 'event_background', 'allow_presale', 
            'presale_start', 'presale_ends_before', 'allow_door_selling', 'check_timeout_orders_interval',
            'enable_ticket_statistics_sending', 'ticket_statistics_email', 'ticket_statistics_interval',
            'ticket_statistics_start', 'ticket_statistics_end', 'display_invoice_info', 'invoice_background',
            'invoice_logo', 'invoice_company_name', 'invoice_address_1', 'invoice_address_2', 'invoice_city',
            'invoice_postal_code', 'invoice_country', 'invoice_email', 'invoice_phone', 'invoice_vat_id',
            'invoice_tax_rate', 'invoice_padding_top', 'invoice_padding_left', 'invoice_padding_right',
            'invoice_padding_bottom', 'advanced_payment_bank_account_name', 'advanced_payment_bank_name',
            'advanced_payment_iban', 'advanced_payment_swift', 'advanced_payment_reference',
            'advanced_payment_due_days', 'advanced_payment_message', 'is_active'
        ])
        writer.writerow([
            'Sample Branding', 'Cinema Site', 'https://example.com', 'path/to/logo.png', 'path/to/favicon.ico',
            '15', 'path/to/success.mp3', 'path/to/ticket_bg.jpg', 'TRUE', 'path/to/event_bg.jpg', 'TRUE',
            '2023-12-01 00:00:00', '1', 'TRUE', '60', 'TRUE', 'stats@example.com', '24',
            '2023-12-01 00:00:00', '2023-12-31 23:59:59', 'TRUE', 'path/to/invoice_bg.jpg', 'path/to/invoice_logo.png',
            'Cinema Company Ltd', 'Main Street 123', 'Suite 456', 'Helsinki', '00100', 'Finland',
            'invoice@example.com', '+358 123 456789', 'FI12345678', '24', '10', '10', '10', '10',
            'Cinema Account', 'Sample Bank', 'FI1234567890123456', 'SAMPLEFI', 'RF123456789', '7',
            'Please pay within 7 days', 'TRUE'
        ])
        
        if Branding.objects.count() != 0:
            brandings = Branding.objects.all()
            for branding in brandings:
                writer.writerow([
                    branding.name, branding.site_name, branding.site_url, branding.logo, branding.favicon,
                    branding.order_timeout, branding.success_sound, branding.ticket_background, branding.display_seat_number,
                    branding.event_background, branding.allow_presale, branding.presale_start, branding.presale_ends_before,
                    branding.allow_door_selling, branding.check_timeout_orders_interval, branding.enable_ticket_statistics_sending,
                    branding.ticket_statistics_email, branding.ticket_statistics_interval, branding.ticket_statistics_start,
                    branding.ticket_statistics_end, branding.display_invoice_info, branding.invoice_background, branding.invoice_logo,
                    branding.invoice_company_name, branding.invoice_address_1, branding.invoice_address_2, branding.invoice_city,
                    branding.invoice_postal_code, branding.invoice_country, branding.invoice_email, branding.invoice_phone,
                    branding.invoice_vat_id, branding.invoice_tax_rate, branding.invoice_padding_top, branding.invoice_padding_left,
                    branding.invoice_padding_right, branding.invoice_padding_bottom, branding.advanced_payment_bank_account_name,
                    branding.advanced_payment_bank_name, branding.advanced_payment_iban, branding.advanced_payment_swift,
                    branding.advanced_payment_reference, branding.advanced_payment_due_days, branding.advanced_payment_message,
                    branding.is_active
                ])
        
        return response
