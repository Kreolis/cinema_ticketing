from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
from .models import Order, ServiceFee

from events.models import is_admin_user, is_ticket_manager_user

def is_accountant_user(user):
    return user.groups.filter(name='Accountants').exists()

def is_admin_or_accountant_user(user):
    return is_admin_user(user) or is_accountant_user(user)


class ServiceFeeAdminForm(forms.ModelForm):
    class Meta:
        model = ServiceFee
        fields = "__all__"

    def clean_payment_method(self):
        payment_method = self.cleaned_data["payment_method"]
        if payment_method not in settings.PAYMENT_VARIANTS:
            raise forms.ValidationError(
                _("The selected payment method is currently disabled in settings.")
            )
        return payment_method

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
            # Filter in Python for orders that have timed out
            timed_out_orders = [order for order in queryset if order.has_timed_out]
            return queryset.filter(id__in=[order.id for order in timed_out_orders])
        elif self.value() == 'no':
            # Filter in Python for orders that have NOT timed out
            active_orders = [order for order in queryset if not order.has_timed_out]
            return queryset.filter(id__in=[order.id for order in active_orders])
        return queryset

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'is_confirmed', 'variant', 'total', 'created' , 'modified', 'has_timed_out', 'show_invoice_pdf')
    list_filter = ('status', 'created', 'is_confirmed', 'variant', TimedOutFilter)
    search_fields = ('id', 'total', 'status')
    actions = ['custom_delete_selected']

    def has_view_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_ticket_manager_user(request.user) or is_accountant_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_accountant_user(request.user):
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_accountant_user(request.user):
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_accountant_user(request.user):
            return True
        return False

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


@admin.register(ServiceFee)
class ServiceFeeAdmin(admin.ModelAdmin):
    form = ServiceFeeAdminForm
    list_display = ('payment_method', 'display_name', 'fee_type', 'fee_amount', 'is_active')
    list_filter = ('payment_method', 'price_classes', 'fee_type', 'is_active')
    search_fields = ('payment_method', 'display_name', 'fee_type')

    def has_view_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group and 'ticketmaster' group to view."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_ticket_manager_user(request.user) or is_accountant_user(request.user):
            return True
        return False

    def has_add_permission(self, request):
        """Allow superusers and users in 'admin' group to add."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_accountant_user(request.user):
            return True
        return False

    def has_change_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to change."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_accountant_user(request.user):
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow superusers and users in 'admin' group to delete."""
        if request.user.is_superuser:
            return True
        if is_admin_user(request.user) or is_accountant_user(request.user):
            return True
        return False


