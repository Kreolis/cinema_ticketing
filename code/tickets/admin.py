from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'total', 'created')
    list_filter = ('status', 'created')
    search_fields = ('id', 'total', 'status')