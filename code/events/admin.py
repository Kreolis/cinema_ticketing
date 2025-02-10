from django.contrib import admin
from .models import Location, PriceClass, Event, Ticket

from django.urls import reverse
from django.utils.html import format_html
import csv
from django.shortcuts import redirect, render
from django.urls import path
from django import forms
from django.http import HttpResponse
from datetime import datetime, timedelta

class CSVImportForm(forms.Form):
    csv_file = forms.FileField(label='CSV file')

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_seats')

@admin.register(PriceClass)
class PriceClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1  # Number of empty forms for adding new tickets
    fields = ('seat', 'email', 'price_class', 'activated', 'sold_as')  # Fields to display in the inline

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('event', 'seat', 'email', 'price_class', 'sold_as', 'activated', 'show_pdf_action', 'send_ticket_email_single')
    actions = ['send_ticket_email_selected']
    list_filter = ('sold_as', 'activated')
    search_fields = ('id', 'event', 'sold_as')

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
    search_fields = ('name', 'location')
    
    inlines = [TicketInline]  # Add tickets inline within the event admin page

    change_list_template = "admin_events_custom.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.import_csv, name='import_csv'),
            path('download-template-csv/', self.download_template_csv, name='download_template_csv'),
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
                    start_time = datetime.strptime(event_data["start_time"], time_format)
                    duration_parts = event_data["duration"].split(':')
                    duration = timedelta(hours=int(duration_parts[0]), minutes=int(duration_parts[1]))
                    presale_start = datetime.strptime(event_data["presale_start"], time_format) if event_data.get("presale_start") else None
                    event = Event.objects.create(
                        name=event_data["name"],
                        start_time=start_time,
                        duration=duration,
                        location=Location.objects.get(name=event_data["location"]),
                        program_link=event_data.get("program_link"),
                        is_active=event_data.get("is_active") == 'True',
                        custom_seats=int(event_data.get("custom_seats")),
                        ticket_background=event_data.get("ticket_background"),
                        display_seat_number=event_data.get("display_seat_number") == 'True',
                        event_background=event_data.get("event_background"),
                        allow_presale=event_data.get("allow_presale") == 'True',
                        presale_start=presale_start,
                        presale_ends_before=int(event_data.get("presale_ends_before")),
                        allow_door_selling=event_data.get("allow_door_selling") == 'True'
                    )
                    price_classes = event_data.get("price_classes").split(',')
                    for price_class_name in price_classes:
                        price_class = PriceClass.objects.get(name=price_class_name.strip())
                        event.price_classes.add(price_class)
                self.message_user(request, "Events imported successfully.")
                return redirect("..")
            except Exception as e:
                error_message = f"Error importing CSV file: {str(e)}"
                form = CSVImportForm()
                payload = {"form": form, "error_message": error_message}
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
