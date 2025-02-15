from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from .models import Order

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'total', 'created', 'show_invoice_pdf')
    list_filter = ('status', 'created')
    search_fields = ('id', 'total', 'status')
    actions = ['custom_delete_selected']

    def show_invoice_pdf(self, obj):
        return format_html(
            '<a class="button" href="{}" target="_blank">Generate PDF</a>&nbsp;',
            reverse('show_generated_invoice', args=[obj.session_id]),
        )
    show_invoice_pdf.short_description = 'Show Invoice PDF'
    show_invoice_pdf.allow_tags = True

    def delete_model(self, request, obj):
        if obj.delete(request):
            messages.success(request, "")
        else:
            messages.error(request, "")

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            if obj.delete(request):
                messages.success(request, "")
            else:
                messages.error(request, "")

    def custom_delete_selected(self, request, queryset):
        for obj in queryset:
            if obj.delete(request):
                messages.success(request, "")
            else:
                messages.error(request, _(""))
    custom_delete_selected.short_description = _("Delete selected orders")

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
