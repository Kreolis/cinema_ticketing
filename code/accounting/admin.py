from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'total', 'created', 'show_invoice_pdf')
    list_filter = ('status', 'created')
    search_fields = ('id', 'total', 'status')

    def show_invoice_pdf(self, obj):
        return format_html(
            '<a class="button" href="{}" target="_blank">Generate PDF</a>&nbsp;',
            reverse('show_generated_invoice', args=[obj.session_id]),
        )
    show_invoice_pdf.short_description = 'Show Invoice PDF'
    show_invoice_pdf.allow_tags = True
