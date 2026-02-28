from django.contrib import admin
from .models import Location, PriceClass, Event, Ticket
from .views import get_ticketmaster_for_user

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

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_seats')
    change_list_template = "admin_locations_custom.html"

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
            path('import-csv/', self.import_csv, name='import_locations_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_locations_template_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
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
            path('import-csv/', self.import_csv, name='import_price_classes_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_price_classes_template_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
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

    def has_view_permission(self, request):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if request.user.groups.filter(name='admin').exists() or request.user.groups.filter(name='Ticket Managers').exists():
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists() or request.user.groups.filter(name='Ticket Managers').exists():
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        if request.user.groups.filter(name='Ticket Managers').exists():
            ticket_master = get_ticketmaster_for_user(request.user)
            # filter displayed tickets based on active locations of the ticket manager
            active_locations = ticket_master.active_locations.all()
            if obj and obj.event.location not in active_locations:
                return False
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        if request.user.groups.filter(name='Ticket Managers').exists():
            ticket_master = get_ticketmaster_for_user(request.user)
            # filter displayed tickets based on active locations of the ticket manager
            active_locations = ticket_master.active_locations.all()
            if obj and obj.event.location not in active_locations:
                return False
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

    def has_view_permission(self, request):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        # Check if user is in 'admin' group
        if request.user.groups.filter(name='admin').exists() or request.user.groups.filter(name='Ticket Managers').exists():
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists() or request.user.groups.filter(name='Ticket Managers').exists():
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        if request.user.groups.filter(name='Ticket Managers').exists():
            ticket_master = get_ticketmaster_for_user(request.user)
            # filter displayed tickets based on active locations of the ticket manager
            active_locations = ticket_master.active_locations.all()
            if obj and obj.event.location not in active_locations:
                return False
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if request.user.groups.filter(name='admin').exists():
            return True
        if request.user.groups.filter(name='Ticket Managers').exists():
            ticket_master = get_ticketmaster_for_user(request.user)
            # filter displayed tickets based on active locations of the ticket manager
            active_locations = ticket_master.active_locations.all()
            if obj and obj.event.location not in active_locations:
                return False
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv, name='import_events_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_events_template_csv'),
        ]
        return custom_urls + urls

    def import_csv(self, request):        
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            try:
                reader = csv.reader(csv_file.read().decode('utf-8').splitlines())
                headers = next(reader)
                for row in reader:
                    time_format = '%Y-%m-%d %H:%M:%S'

                    event_data = dict(zip(headers, row))
                    
                    start_time = timezone.make_aware(datetime.strptime(event_data["start_time"], time_format))
                    
                    duration_parts = event_data["duration"].split(':')
                    duration = timedelta(hours=int(duration_parts[0]), minutes=int(duration_parts[1]))
                    
                    presale_start = timezone.make_aware(datetime.strptime(event_data["presale_start"], time_format)) if event_data.get("presale_start") else None
                    
                    location = Location.objects.get_or_create(name=event_data["location"])[0]
     
                    event = Event.objects.create(
                        name=event_data["name"],
                        start_time=start_time,
                        duration=duration,
                        location=location,
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

                    if event_data.get("ticket_background"):
                        event.ticket_background = event_data.get("ticket_background")

                    if event_data.get("display_seat_number"):
                        event.display_seat_number = event_data.get("display_seat_number", "").upper() == 'TRUE'
                    
                    if event_data.get("event_background"):
                        event.event_background = event_data.get("event_background")

                    if event_data.get("allow_presale"):
                        event.allow_presale = event_data.get("allow_presale", "").upper() == 'TRUE'

                    if presale_start:
                        event.presale_start = presale_start

                    if event_data.get("presale_ends_before"):
                        event.presale_ends_before = int(event_data.get("presale_ends_before"))

                    if event_data.get("allow_door_selling"):
                        event.allow_door_selling = event_data.get("allow_door_selling", "").upper() == 'TRUE'

                    event.save()
                    logger.info(f"Event saved: {event}")

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
        writer.writerow([
            'name', 'start_time', 'duration', 'location', 'price_classes', 'program_link', 'is_active', 
            'custom_seats', 'ticket_background', 'display_seat_number', 'event_background', 'allow_presale', 
            'presale_start', 'presale_ends_before', 'allow_door_selling'
        ])
        if PriceClass.objects.count() == 0:
            price_classes = 'Price Class 1, Price Class 2'
        else:
            price_classes = ', '.join([pc.name for pc in PriceClass.objects.all()])
        if Location.objects.count() == 0:
            locations = ['Location 1']
        else:  
            locations = [loc.name for loc in Location.objects.all()]

        for counter, location in enumerate(locations):
            writer.writerow([
                f'Sample Event {counter}', '2023-12-31 18:00:00', '2:00', location, price_classes, 
                'http://example.com', 'True', '100', 'path/to/ticket_background.jpg', 'True', 
                'path/to/event_background.jpg', 'True', '2023-12-01 00:00:00', '1', 'True'
            ])

        if Event.objects.count() != 0:
            events = Event.objects.all()
            for event in events:
                writer.writerow([
                    event.name, event.start_time, event.duration, event.location.name, price_classes, 
                    event.program_link, event.is_active, event.custom_seats, event.ticket_background, 
                    event.display_seat_number, event.event_background, event.allow_presale, 
                    event.presale_start, event.presale_ends_before, event.allow_door_selling
                ])
        return response
