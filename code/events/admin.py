from django.contrib import admin
from .models import Location, PriceClass, Event, Ticket

from django.urls import reverse
from django.utils.html import format_html


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
        if obj.email:
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
