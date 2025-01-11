from django.contrib import admin
from .models import Location, PriceClass, Event, Ticket

from .utils import generate_pdf_ticket

import io

from django.urls import path, reverse
from django.http import FileResponse
from django.utils.html import format_html

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_seats')

@admin.register(PriceClass)
class PriceClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')

# Define the action in the Inline admin
def generate_pdf_action_view(request, ticket_id):
    # Fetch the ticket by ID
    ticket = Ticket.objects.get(pk=ticket_id)
    
    # Generate PDF for the selected ticket
    pdf = generate_pdf_ticket(ticket)
    # Create a BytesIO stream to hold the PDF data
    file_stream = io.BytesIO(pdf.output())

    # Create a FileResponse to send the PDF file
    response = FileResponse(file_stream, content_type='application/pdf', filename="ticket_{ticket.id}.pdf")
    
    return response

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1  # Number of empty forms for adding new tickets
    fields = ('seat', 'price_class', 'activated', 'sold')  # Fields to display in the inline

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('event', 'seat', 'price_class', 'sold', 'activated', 'ticket_actions')
    list_filter = ('sold', 'activated')
    search_fields = ('id', 'event', 'sold')

    # Add custom action buttons
    def ticket_actions(self, obj):
        return format_html(
            '<a class="button" href="{}" target="_blank">Generate PDF</a>&nbsp;',
            reverse('admin:generate_pdf_action', args=[obj.pk]),
        )
    ticket_actions.short_description = 'Ticket Actions'
    ticket_actions.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('ticket_<uuid:ticket_id>.pdf', self.admin_site.admin_view(generate_pdf_action_view), name='generate_pdf_action'),
        ]
        return custom_urls + urls

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'location')
    list_filter = ('location', 'start_time')
    search_fields = ('name', 'location')
    
    inlines = [TicketInline]  # Add tickets inline within the event admin page
    