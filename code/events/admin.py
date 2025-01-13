from django.contrib import admin
from .models import Location, PriceClass, Event, Ticket

import io

from django.urls import path, reverse
from django.http import FileResponse, HttpResponse
from django.utils.html import format_html
from django.shortcuts import get_object_or_404

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
    pdf = ticket.generate_pdf_ticket()
    # Create a BytesIO stream to hold the PDF data
    file_stream = io.BytesIO(pdf.output())

    # Create a FileResponse to send the PDF file
    response = FileResponse(file_stream, content_type='application/pdf', filename="ticket_{ticket.id}.pdf")
    
    return response

def send_ticket_email_view(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if ticket.email:
        ticket.send_to_email()
        return HttpResponse("Email sent successfully.")
    return HttpResponse("No email address provided.")

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1  # Number of empty forms for adding new tickets
    fields = ('seat', 'email', 'price_class', 'activated', 'sold')  # Fields to display in the inline

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('event', 'seat', 'email', 'price_class', 'sold', 'activated', 'show_pdf_action', 'send_ticket_email')
    actions = ['send_ticket_email_action']
    list_filter = ('sold', 'activated')
    search_fields = ('id', 'event', 'sold')

    # Add custom action buttons
    def show_pdf_action(self, obj):
        return format_html(
            '<a class="button" href="{}" target="_blank">Generate PDF</a>&nbsp;',
            reverse('admin:generate_pdf_action', args=[obj.pk]),
        )
    show_pdf_action.short_description = 'Show PDF'
    show_pdf_action.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('ticket_<uuid:ticket_id>.pdf', self.admin_site.admin_view(generate_pdf_action_view), name='generate_pdf_action'),
            path('send_ticket_email/<uuid:ticket_id>/', self.admin_site.admin_view(send_ticket_email_view), name='send_ticket_email'),
        ]
        return custom_urls + urls

    def send_ticket_email(self, obj):
        if obj.email:
            return format_html('<a class="button" href="{}">Send Email</a>', reverse('admin:send_ticket_email', args=[obj.id]))
        return "No Email"

    send_ticket_email.short_description = 'Send Ticket Email'
    send_ticket_email.allow_tags = True

    def send_ticket_email_action(self, request, queryset):
        for ticket in queryset:
            if ticket.email:
                ticket.send_to_email()
        self.message_user(request, "Emails sent successfully.")

    send_ticket_email_action.short_description = "Send Ticket Email"

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'location')
    list_filter = ('location', 'start_time')
    search_fields = ('name', 'location')
    
    inlines = [TicketInline]  # Add tickets inline within the event admin page
