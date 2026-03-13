from django.contrib import admin, messages
from .models import Location, PriceClass, Event, Ticket, TicketMaster

from django.urls import reverse
from django.utils.html import format_html
import csv
from django.shortcuts import redirect, render
from django.urls import path
from django import forms
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.utils.dateparse import parse_datetime
from datetime import datetime, timedelta
from django.utils import timezone
from pytz import timezone as pytz_timezone

import logging

logger = logging.getLogger(__name__)

from branding.models import get_active_branding


def is_admin_user(user):
    return user.is_superuser or user.groups.filter(name__in=['admin', 'Admins']).exists()


def is_ticket_manager_user(user):
    return user.groups.filter(name='Ticket Managers').exists()


def get_ticketmaster_for_user(user):
    return TicketMaster.for_user(user)


def get_user_active_locations(user):
    if is_admin_user(user):
        return None
    if not is_ticket_manager_user(user):
        return Location.objects.none()

    ticket_master = get_ticketmaster_for_user(user)
    if not ticket_master:
        return Location.objects.none()

    active_locations = ticket_master.active_locations.all()
    if active_locations.exists():
        return active_locations
    return None

class CSVImportForm(forms.Form):
    csv_file = forms.FileField(label='CSV file')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_seats')
    change_list_template = "admin_locations_custom.html"

    def has_view_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if is_admin_user(request.user) or is_ticket_manager_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv, name='import_locations_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_locations_template_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            try:
                reader = csv.reader(csv_file.read().decode('utf-8').splitlines())
                headers = next(reader)
                for row in reader:
                    location_data = dict(zip(headers, row))
                    
                    location = Location.objects.create(
                        name=location_data["name"],
                        total_seats=int(location_data["total_seats"]),
                        street=location_data.get("street", ""),
                        house_number=location_data.get("house_number", ""),
                        city=location_data.get("city", ""),
                        zip_code=location_data.get("zip_code", ""),
                    )
                    logger.info(f"Created location: {location}")

                self.message_user(request, "Locations imported successfully.")
                return redirect("..")
            except Exception as e:
                error_message = f"Error importing CSV file: {str(e)}"
                form = CSVImportForm()
                payload = {"form": form, "error_message": error_message}
                logger.error(error_message)
                return render(request, "locations_import_csv_form.html", payload)
            
        form = CSVImportForm()
        payload = {"form": form}
        return render(request, "locations_import_csv_form.html", payload)

    def download_template_csv(self, request):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="location_import_template.csv"'},
        )
        writer = csv.writer(response)
        writer.writerow(['name', 'total_seats', 'street', 'house_number', 'city', 'zip_code'])
        writer.writerow(['Sample Location 1', '100', 'Main Street', '123', 'Helsinki', '00100'])
        writer.writerow(['Sample Location 2', '150', 'Park Avenue', '456', 'Espoo', '02100'])
        
        if Location.objects.count() != 0:
            locations = Location.objects.all()
            for location in locations:
                writer.writerow([location.name, location.total_seats, location.street, location.house_number, location.city, location.zip_code])
        
        return response

@admin.register(PriceClass)
class PriceClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')
    change_list_template = "admin_price_classes_custom.html"

    def has_view_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if is_admin_user(request.user) or is_ticket_manager_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv, name='import_price_classes_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_price_classes_template_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            try:
                reader = csv.reader(csv_file.read().decode('utf-8').splitlines())
                headers = next(reader)
                for row in reader:
                    price_class_data = dict(zip(headers, row))
                    
                    price_class = PriceClass.objects.create(
                        name=price_class_data["name"],
                        price=float(price_class_data["price"]),
                        notification_message=price_class_data.get("notification_message", ""),
                        secret=price_class_data.get("secret", "").upper() == 'TRUE',
                    )
                    logger.info(f"Created price class: {price_class}")

                self.message_user(request, "Price classes imported successfully.")
                return redirect("..")
            except Exception as e:
                error_message = f"Error importing CSV file: {str(e)}"
                form = CSVImportForm()
                payload = {"form": form, "error_message": error_message}
                logger.error(error_message)
                return render(request, "price_classes_import_csv_form.html", payload)
            
        form = CSVImportForm()
        payload = {"form": form}
        return render(request, "price_classes_import_csv_form.html", payload)

    def download_template_csv(self, request):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="price_class_import_template.csv"'},
        )
        writer = csv.writer(response)
        writer.writerow(['name', 'price', 'notification_message', 'secret'])
        writer.writerow(['Standard', '15.00', 'Standard ticket', 'True'])
        writer.writerow(['Premium', '25.00', 'Premium ticket with extras', 'False'])
        
        if PriceClass.objects.count() != 0:
            price_classes = PriceClass.objects.all()
            for price_class in price_classes:
                writer.writerow([price_class.name, price_class.price, price_class.notification_message, price_class.secret])
        
        return response

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1  # Number of empty forms for adding new tickets
    fields = ('seat', 'email', 'price_class', 'activated', 'sold_as')  # Fields to display in the inline

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('event', 'seat', 'email', 'price_class', 'sold_as', 'activated', 'show_pdf_action', 'send_ticket_email_single')
    actions = ['send_ticket_email_selected']
    list_filter = ('sold_as', 'activated')
    search_fields = ('id', 'event__name', 'sold_as')  # Updated search_fields

    def has_view_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if is_admin_user(request.user) or is_ticket_manager_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        active_locations = get_user_active_locations(request.user)
        if active_locations is None:
            return queryset
        return queryset.filter(event__location__in=active_locations)

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    # Add custom action buttons
    def show_pdf_action(self, obj):
        return format_html(
            '<a class="button" href="{}" target="_blank">Generate PDF</a>&nbsp;',
            reverse('show_generated_ticket_pdf', args=[obj.pk]),
        )
    show_pdf_action.short_description = 'Show PDF'
    show_pdf_action.allow_tags = True

    def send_ticket_email_single(self, obj):
        if (obj.email):
            response = reverse('send_ticket_email', args=[obj.id])
            return format_html(
                '<a class="button" href="{}" onclick="fetch(\'{}\').then(response => response.json()).then(data => this.outerHTML = `<pre>${{JSON.stringify(data, null, 2)}}</pre>`); return false;">Send Email</a>',
                response, response
            )
        return "No Email"

    send_ticket_email_single.short_description = 'Send Ticket Email'
    send_ticket_email_single.allow_tags = True

    def send_ticket_email_selected(self, request, queryset):
        for ticket in queryset:
            if ticket.email:
                ticket.send_to_email()
        self.message_user(request, "Emails sent successfully.")

    send_ticket_email_selected.short_description = "Send Ticket Email"

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'location')
    list_filter = ('location', 'start_time')
    search_fields = ('name', 'location__name')  # Updated search_fields
    
    inlines = [TicketInline]  # Add tickets inline within the event admin page

    change_list_template = "admin_events_custom.html"

    def has_view_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if is_admin_user(request.user) or is_ticket_manager_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def _get_event_timezone(self, event=None):
        if event and event.custom_event_timezone:
            try:
                return pytz_timezone(event.custom_event_timezone)
            except Exception as e:
                logger.error(
                    f"Invalid custom_event_timezone '{event.custom_event_timezone}' "
                    f"on event pk={event.pk}: {e}"
                )

        branding = get_active_branding()
        if branding and branding.default_event_timezone:
            try:
                return pytz_timezone(branding.default_event_timezone)
            except Exception as e:
                logger.error(
                    f"Invalid default_event_timezone '{branding.default_event_timezone}' "
                    f"in branding settings: {e}"
                )

        return timezone.get_default_timezone()

    def add_view(self, request, form_url='', extra_context=None):
        with timezone.override(self._get_event_timezone()):
            return super().add_view(request, form_url=form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        event = Event.objects.filter(pk=object_id).first()
        with timezone.override(self._get_event_timezone(event)):
            return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        active_locations = get_user_active_locations(request.user)
        if active_locations is None:
            return queryset
        return queryset.filter(location__in=active_locations)

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        if is_ticket_manager_user(request.user):
            active_locations = get_user_active_locations(request.user)
            if active_locations is None:
                return True
            if obj is None:
                return True
            return obj.location in active_locations
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        if is_ticket_manager_user(request.user):
            active_locations = get_user_active_locations(request.user)
            if active_locations is None:
                return True
            if obj is None:
                return True
            return obj.location in active_locations
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv, name='import_events_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_events_template_csv'),
        ]
        return custom_urls + urls

    def _parse_csv_datetime(self, value, import_timezone):
        value = (value or '').strip()
        if not value:
            return None

        parsed = parse_datetime(value)
        if parsed is None:
            parsed = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')

        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, import_timezone)

        return parsed

    def _serialize_csv_datetime(self, value):
        if value is None:
            return ''
        if timezone.is_aware(value):
            return value.isoformat(sep=' ')
        return value.strftime('%Y-%m-%d %H:%M:%S')

    def import_csv(self, request):        
        if not self.has_add_permission(request):
            raise PermissionDenied
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            try:
                default_import_timezone = self._get_event_timezone()
                reader = csv.reader(csv_file.read().decode('utf-8').splitlines())
                headers = next(reader)
                import_warnings = []
                for row in reader:
                    event_data = dict(zip(headers, row))
                    location_name = (event_data.get("location") or "").strip()
                    location_total_seats_raw = (event_data.get("location_total_seats") or "").strip()

                    custom_tz_name = (event_data.get("custom_event_timezone") or "").strip()
                    if custom_tz_name:
                        try:
                            import_timezone = pytz_timezone(custom_tz_name)
                        except Exception as tz_err:
                            warn_msg = (
                                f"Row '{event_data.get('name', '?')}': invalid timezone "
                                f"'{custom_tz_name}' ({tz_err}) — falling back to default timezone."
                            )
                            logger.warning(warn_msg)
                            import_warnings.append(warn_msg)
                            import_timezone = default_import_timezone
                            custom_tz_name = ""  # don't persist the invalid value
                    else:
                        import_timezone = default_import_timezone

                    start_time = self._parse_csv_datetime(event_data["start_time"], import_timezone)
                    
                    duration_parts = event_data["duration"].split(':')
                    duration = timedelta(hours=int(duration_parts[0]), minutes=int(duration_parts[1]))
                    
                    presale_start = self._parse_csv_datetime(event_data.get("presale_start"), import_timezone)

                    location = Location.objects.filter(name=location_name).first()
                    if location is None:
                        if not location_total_seats_raw:
                            raise ValueError(
                                f"Location '{location_name}' does not exist. Provide location_total_seats in the CSV or create the location first."
                            )
                        try:
                            location_total_seats = int(location_total_seats_raw)
                        except ValueError as exc:
                            raise ValueError(
                                f"Location '{location_name}' has invalid location_total_seats '{location_total_seats_raw}'."
                            ) from exc
                        if location_total_seats <= 0:
                            raise ValueError(
                                f"Location '{location_name}' must have a positive location_total_seats value."
                            )

                        location, _ = Location.objects.get_or_create(
                            name=location_name,
                            defaults={'total_seats': location_total_seats},
                        )
     
                    event = Event.objects.create(
                        name=event_data["name"],
                        start_time=start_time,
                        duration=duration,
                        location=location,
                        custom_event_timezone=custom_tz_name or None,
                    )
                    logger.info(f"Created event: {event}")
                    
                    if event_data.get("price_classes"):
                        price_classes = event_data["price_classes"].split(',')
                        for price_class in price_classes:
                            price_class = price_class.strip()
                            # try to find from existing price classes
                            event.price_classes.add(PriceClass.objects.get_or_create(name=price_class, defaults={'price': 0})[0])
                    
                    if event_data.get("program_link"):
                        event.program_link = event_data.get("program_link")
                    
                    if event_data.get("is_active"):
                        event.is_active = event_data.get("is_active", "").upper() == 'TRUE'

                    if event_data.get("custom_seats"):
                        event.custom_seats = int(event_data.get("custom_seats"))

                    if event_data.get("custom_ticket_background"):
                        event.custom_ticket_background = event_data.get("custom_ticket_background")

                    if event_data.get("display_seat_number"):
                        event.custom_display_seat_number = event_data.get("display_seat_number", "").upper() == 'TRUE'

                    if event_data.get("custom_event_background"):
                        event.custom_event_background = event_data.get("custom_event_background")

                    if event_data.get("allow_presale"):
                        event.custom_allow_presale = event_data.get("allow_presale", "").upper() == 'TRUE'

                    if presale_start:
                        event.custom_presale_start = presale_start

                    if event_data.get("presale_ends_before"):
                        event.custom_presale_ends_before = int(event_data.get("presale_ends_before"))

                    if event_data.get("allow_door_selling"):
                        event.custom_allow_door_selling = event_data.get("allow_door_selling", "").upper() == 'TRUE'

                    event.save()
                    logger.info(f"Event saved: {event}")

                if import_warnings:
                    for w in import_warnings:
                        self.message_user(request, w, level=messages.WARNING)
                self.message_user(request, "Events imported successfully.")
                return redirect("..")
            except Exception as e:
                error_message = f"Error importing CSV file: {str(e)}"
                form = CSVImportForm()
                payload = {"form": form, "error_message": error_message}
                logger.error(error_message)
                return render(request, "events_import_csv_form.html", payload)
            
        form = CSVImportForm()
        payload = {"form": form}
        return render(request, "events_import_csv_form.html", payload)

    def download_template_csv(self, request):
        response = HttpResponse(
            content_type='text/csv',
            headers={'Content-Disposition': 'attachment; filename="event_import_template.csv"'},
        )
        writer = csv.writer(response)

        def serialize_override(value):
            return '' if value is None else value

        writer.writerow([
            'name', 'start_time', 'duration', 'location', 'location_total_seats', 'price_classes', 'program_link', 'is_active',
            'custom_seats', 'custom_ticket_background', 'display_seat_number', 'custom_event_background', 'allow_presale',
            'presale_start', 'presale_ends_before', 'allow_door_selling', 'custom_event_timezone'
        ])
        if PriceClass.objects.count() == 0:
            price_classes = 'Price Class 1, Price Class 2'
        else:
            price_classes = ', '.join([pc.name for pc in PriceClass.objects.all()])
        if Location.objects.count() == 0:
            locations = [('Location 1', 100)]
        else:  
            locations = [(loc.name, loc.total_seats) for loc in Location.objects.all()]

        for counter, (location, location_total_seats) in enumerate(locations):
            writer.writerow([
                f'Sample Event {counter}', '2023-12-31 18:00:00', '2:00', location, location_total_seats, price_classes,
                'http://example.com', 'True', '100', '', 'True',
                '', 'True', '2023-12-01 00:00:00', '1', 'True', ''
            ])

        if Event.objects.count() != 0:
            events = Event.objects.all()
            for event in events:
                writer.writerow([
                    event.name, self._serialize_csv_datetime(event.start_time), event.duration, event.location.name, event.location.total_seats, price_classes,
                    event.program_link, event.is_active, event.custom_seats,
                    event.custom_ticket_background.name if event.custom_ticket_background else '',
                    serialize_override(event.custom_display_seat_number),
                    event.custom_event_background.name if event.custom_event_background else '',
                    serialize_override(event.custom_allow_presale),
                    self._serialize_csv_datetime(event.custom_presale_start),
                    serialize_override(event.custom_presale_ends_before),
                    serialize_override(event.custom_allow_door_selling),
                    event.custom_event_timezone or ''
                ])
        return response

@admin.register(TicketMaster)
class TicketMasterAdmin(admin.ModelAdmin):
    list_display = ('firstname', 'lastname', 'email', 'user', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('firstname', 'lastname', 'email', 'user__username', 'user__email')

    def has_view_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if is_admin_user(request.user) or is_ticket_manager_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user):
            return True
        return False