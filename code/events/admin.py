from django.contrib import admin
from .models import Location, PriceClass, Event

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_seats')

@admin.register(PriceClass)
class PriceClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'price')

from tickets.models import Ticket
class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1  # Number of empty forms for adding new tickets
    fields = ('seat', 'price_class', 'activated', 'sold')  # Fields to display in the inline

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_time', 'location')
    list_filter = ('location', 'start_time')
    search_fields = ('name', 'location')
    
    inlines = [TicketInline]  # Add tickets inline within the event admin page
    