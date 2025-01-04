from django.contrib import admin
from .models import Payment

from events.models import Ticket

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('event', 'seat', 'price_class', 'sold', 'activated')
    list_filter = ('sold', 'activated')
    search_fields = ('id', 'event', 'sold')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'total', 'created')
    list_filter = ('status', 'created')
    search_fields = ('id', 'total', 'status')