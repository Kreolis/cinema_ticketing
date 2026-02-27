from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django.db.models import F, ExpressionWrapper, DurationField
from django.db.models.functions import Now
from .models import Order

class TimedOutFilter(SimpleListFilter):
    title = _('Timed Out')
    parameter_name = 'timed_out'

    def lookups(self, request, model_admin):
        return (
            ('yes', _('Yes')),
            ('no', _('No')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            timeout_duration = ExpressionWrapper(
                F('timeout') * 60,  # Convert minutes to seconds
                output_field=DurationField()
            )
            return queryset.annotate(
                timeout_threshold=Now() - timeout_duration
            ).filter(
                modified__lt=F('timeout_threshold')
            )
        elif self.value() == 'no':
            timeout_duration = ExpressionWrapper(
                F('timeout') * 60,  # Convert minutes to seconds
                output_field=DurationField()
            )
            return queryset.annotate(
                timeout_threshold=Now() - timeout_duration
            ).exclude(
                modified__lt=F('timeout_threshold')
            )

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'is_confirmed', 'variant', 'total', 'created' , 'modified', 'has_timed_out', 'show_invoice_pdf')
    list_filter = ('status', 'created', 'is_confirmed', 'variant', TimedOutFilter)
    search_fields = ('id', 'total', 'status')
    actions = ['custom_delete_selected']

    def show_invoice_pdf(self, obj):
        return format_html(
            '<a class="button" href="{}" target="_blank">Show Invoice</a>&nbsp;',
            reverse('show_generated_invoice', args=[obj.session_id]),
        )
    show_invoice_pdf.short_description = 'Invoice'
    show_invoice_pdf.allow_tags = True

    def delete_model(self, request, obj):
        try:
            obj.delete()
            messages.success(request, f"Order {obj.id} deleted successfully")
        except Exception as e:
            messages.error(request, f"Error deleting order {obj.id}: {str(e)}")

    def delete_queryset(self, request, queryset):
        count = queryset.count()
        success_count = 0
        error_count = 0
        for obj in queryset:
            try:
                obj.delete()
                success_count += 1
            except Exception as e:
                error_count += 1
                messages.error(request, f"Error deleting order {obj.id}: {str(e)}")
        if success_count > 0:
            messages.success(request, f"{success_count}/{count} orders deleted successfully")
        if error_count > 0:
            messages.warning(request, f"{error_count}/{count} orders failed to delete")

    def custom_delete_selected(self, request, queryset):
        count = queryset.count()
        success_count = 0
        error_count = 0
        for obj in queryset:
            try:
                obj.delete()
                success_count += 1
            except Exception as e:
                error_count += 1
                messages.error(request, f"Error deleting order {obj.id}: {str(e)}")
        if success_count > 0:
            messages.success(request, f"{success_count}/{count} orders deleted successfully")
        if error_count > 0:
            messages.warning(request, f"{error_count}/{count} orders failed to delete")
    custom_delete_selected.short_description = _("Delete selected orders")

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
