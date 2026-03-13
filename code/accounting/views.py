from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login 
from django.contrib.auth import logout as auth_logout
from django.utils.translation import gettext_lazy as _ 

import io
import logging

from django.conf import settings
from django.http import FileResponse, Http404

# django-payments
from payments import get_payment_model, RedirectNeeded
from payments.models import PaymentStatus

from .forms import PaymentInfoForm
from .forms import UpdateEmailsForm 
from .models import get_order_create_defaults

from events.models import SoldAsStatus
from accounting.admin import is_admin_or_accountant_user

logger = logging.getLogger(__name__)

def cart_view(request):
    if not request.session.session_key:
        request.session.create()

    order, _ = get_payment_model().objects.get_or_create(
        session_id=request.session.session_key,
        defaults=get_order_create_defaults(),
    )

    if order.status == PaymentStatus.CONFIRMED:
        # this is an old order that has already been paid
        # create a new session and order
        request.session.cycle_key()
        order, _ = get_payment_model().objects.get_or_create(
            session_id=request.session.session_key,
            defaults=get_order_create_defaults(),
        )

    elif not order.is_valid():
        # this is an old order that has expired
        # delete the order and create a new one
        order.delete()
        order = get_payment_model().objects.create(
            session_id=request.session.session_key,
            **get_order_create_defaults(),
        )

    if request.method == 'POST':
        form = UpdateEmailsForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            for ticket in order.tickets.all():
                ticket.email = email
                ticket.save()
            return redirect('cart_view')
    else:
        form = UpdateEmailsForm()

    time_remaining = order.get_remaining_time()

    # recalculate total in case tickets were added or removed
    order.compute_total(with_service_fees=False)
    return TemplateResponse(request, 'cart.html', {'form': form, 'order': order, 'time_remaining': time_remaining,
        'currency': settings.DEFAULT_CURRENCY})

def order_information_form(request):
    try:
        order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
    except Http404:
        return redirect('cart_view')
        
    if not order.is_valid():
        order.delete()
        order = get_payment_model().objects.create(
            session_id=request.session.session_key,
            **get_order_create_defaults(),
        )
        return redirect('cart_view')
        
    gateway_form = None  # Initialize gateway_form to None

    service_fees = {}
    for variant in settings.PAYMENT_VARIANTS.keys():
        service_fees[variant] = order.get_total_service_fee_amount(variant=variant)

    if request.method == 'POST':
        order.reset_timeout()
        form = PaymentInfoForm(service_fees=service_fees, data=request.POST)  # Pass service fees to the form to display in the choices
        
        if form.is_valid():
            form_fields = form.cleaned_data
            # update the order with the form data
            order.billing_first_name = form_fields["billing_first_name"]
            order.billing_last_name = form_fields["billing_last_name"]
            order.billing_address_1 = form_fields["billing_address_1"]
            order.billing_address_2 = form_fields["billing_address_2"]
            order.billing_city = form_fields["billing_city"]
            order.billing_postcode = form_fields["billing_postcode"]
            order.billing_country_code = form_fields["billing_country_code"]
            order.billing_country_area = form_fields["billing_country_area"]
            order.billing_email = form_fields["billing_email"]
            order.billing_phone = form_fields["billing_phone"]

            # enable user to choose payment method
            order.variant = form_fields["payment_method"]

            

            # set the session_id to the current session
            order.session_id = request.session.session_key
            order.change_status(PaymentStatus.WAITING)

            # if the payment variant is able to do a preauth, set the success and failure urls
            # check first if the name of the variant is matching with a variant that has the capture field set to False
            if settings.PAYMENT_VARIANTS[order.variant][1].get('capture') == False:
                order.failure_url = request.build_absolute_uri(reverse('payment_failed'))
                order.success_url = request.build_absolute_uri(reverse('order_payment', args=[order.session_id]))
            else:
                order.failure_url = request.build_absolute_uri(reverse('payment_failed'))
                order.success_url = request.build_absolute_uri(reverse('order_payment_overview'))

            order.save()
            order.compute_total(with_service_fees=True)

            # update tickets so that they have an email address, if none was set before, this is needed to send the payment instructions email or confirmation email
            for ticket in order.tickets.all():
                if ticket.email == None:
                    ticket.email = order.billing_email
                    ticket.save()
            
            return redirect('payment_form', order_id=order.session_id)
    else:
        # Initialize the form with the current order data if order has data
        if order.billing_first_name:
            form = PaymentInfoForm(initial={
                'billing_first_name': order.billing_first_name,
                'billing_last_name': order.billing_last_name,
                'billing_address_1': order.billing_address_1,
                'billing_address_2': order.billing_address_2,
                'billing_city': order.billing_city,
                'billing_postcode': order.billing_postcode,
                'billing_country_code': order.billing_country_code,
                'billing_country_area': order.billing_country_area,
                'billing_email': order.billing_email,
                'billing_phone': order.billing_phone,
                'payment_method': order.variant,
            }, service_fees=service_fees)  # Pass service fees to the form to display in the choices
        else:
            form = PaymentInfoForm(service_fees=service_fees)  # Pass service fees to the form to display in the choices

    time_remaining = order.get_remaining_time()
    return TemplateResponse(request, 'order_information_form.html', 
                  {'form': form,
                   'order': order, 
                   'time_remaining': time_remaining, 
                   'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
                   'currency': settings.DEFAULT_CURRENCY,
                })

def payment_form(request, order_id):
    if not request.session.session_key:
        request.session.create()

    try:
        order = get_object_or_404(get_payment_model(), session_id=order_id)
    except Http404:
        return redirect('cart_view')
    except Exception:
        logger.exception("Unexpected error while fetching order in payment_form: order_id=%s", order_id)
        raise

    if order.session_id != request.session.session_key:
        logger.warning(
            "Blocked payment_form access for order session_id=%s from session_key=%s",
            order.session_id,
            request.session.session_key,
        )
        return redirect('cart_view')

    if not order.is_valid():
        order.delete()
        order = get_payment_model().objects.create(
            session_id=request.session.session_key,
            **get_order_create_defaults(),
        )
        return redirect('cart_view')

    try:
        form = order.get_form(data=request.POST or None)
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))

    time_remaining = order.get_remaining_time()
    return TemplateResponse(request, 'payment_form.html', 
                  {'form': form,
                   'order': order, 
                   'time_remaining': time_remaining,
                   'currency': settings.DEFAULT_CURRENCY, 
                   'humanzied_payment_variant': settings.HUMANIZED_PAYMENT_VARIANT[order.variant]})


def payment_failed(request):
    return TemplateResponse(request, 'payment_failed.html')

def order_payment(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    order.reset_timeout()
    
    time_remaining = order.get_remaining_time()
    return TemplateResponse(request, 'order_payment_overview.html', 
                            {'order': order, 
                             'time_remaining': time_remaining,
                             'currency': settings.DEFAULT_CURRENCY, 
                             'humanzied_payment_variant': settings.HUMANIZED_PAYMENT_VARIANT[order.variant],
                             'service_fees': order.get_service_fees()})

def order_payment_overview(request):
    return order_payment(request, request.session.session_key)

def user_confirm_order(request, order_id):
    if request.method != 'POST':
        return redirect('cart_view')
    
    order = get_object_or_404(get_payment_model(), session_id=order_id)

    if order.status == PaymentStatus.PREAUTH:
        # variant was preauthed therefore capture the payment
        try:
            if not order.variant == 'advance_payment':
                # Capture the payment after review or fulfillment
                order.capture()

                order.change_status(PaymentStatus.CONFIRMED)
                order.is_confirmed = True
                order.save()

                for ticket in order.tickets.all():
                    ticket.sold_as = SoldAsStatus.PRESALE_ONLINE
                    ticket.first_name = order.billing_first_name
                    ticket.last_name = order.billing_last_name
                    ticket.save()
                    ticket.queue_send_to_email()
                    
            else: 
                # variant was advance payment therefore confirm the order
                order.change_status(PaymentStatus.CONFIRMED)
                order.save()

                for ticket in order.tickets.all():
                    ticket.sold_as = SoldAsStatus.PRESALE_ONLINE_WAITING
                    ticket.first_name = order.billing_first_name
                    ticket.last_name = order.billing_last_name
                    ticket.save()
            
        except RedirectNeeded as e:
            return e.response
        
    elif order.status == PaymentStatus.WAITING:

        # variant was not preauthed therefore initiate the payment
        order.failure_url = request.build_absolute_uri(reverse('payment_failed'))
        order.success_url = request.build_absolute_uri(reverse('ticket_list', args=[order_id]))
    
        order.save()

        try:
            order.change_status(PaymentStatus.INPUT)
            # form is not used in view but method will raise RedirectNeeded if the payment provider requires a redirect
            gateway_form = order.get_form(data=request.POST or None)
        except RedirectNeeded as e:
            return redirect(str(e))

    else:
        return redirect('order_information_form')
    
    if not order.is_confirmed and order.variant == 'advance_payment':
        # Send payment instructions email (only for advance/bank-transfer payments)
        order.queue_payment_instructions_email()
    elif order.is_confirmed:
        # Send confirmation and invoice email
        order.queue_confirmation_email()

    # order is processed
    # make sure the user can make a new order by creating a new session
    request.session.cycle_key()
        
    return redirect('ticket_list', order_id=order_id)


def ticket_list(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)

    # order is in INPUT status, basically coming back from the payment provider
    if order.status == PaymentStatus.INPUT:
        order.change_status(PaymentStatus.CONFIRMED)
        if not order.variant == 'advance_payment':
            # order is paid fully and can be confirmed
            order.is_confirmed = True
            order.save()
        # else: the order is not paid yet and will be confirmed later manually        

        for ticket in order.tickets.all():
                ticket.sold_as = SoldAsStatus.PRESALE_ONLINE
                ticket.first_name = order.billing_first_name
                ticket.last_name = order.billing_last_name
                ticket.save()
                if order.is_confirmed:
                    ticket.queue_send_to_email()

        if not order.is_confirmed and order.variant == 'advance_payment':
            # Send payment instructions email (only for advance/bank-transfer payments)
            order.queue_payment_instructions_email()
        elif order.is_confirmed:
            # Send confirmation and invoice email
            order.queue_confirmation_email()

        if request.session.session_key == None:
            logger.info(f"Session key: {request.session.session_key}")
            logger.info("No session key found. Creating new session.")
            request.session.create()
        

        # order is paid
        # make sure the user can make a new order by creating a new session
        while request.session.session_key == order_id:
            logger.info(f"Session key: {request.session.session_key}")
            logger.info("Session key is the same as order ID. Cycling key.")
            request.session.cycle_key()

        logger.info(f"Session key: {request.session.session_key}")
    # if order is payed show the tickets
    if order.status == PaymentStatus.CONFIRMED:
        return TemplateResponse(request, 'ticket_list.html', {
            'order': order,
            'currency': settings.DEFAULT_CURRENCY,
            'payment_instructions': order.get_payment_instructions(),
            'humanzied_payment_variant': settings.HUMANIZED_PAYMENT_VARIANT[order.variant],
            'service_fees': order.get_service_fees()
        })
    else:
        return redirect('order_information_form')
    

def show_generated_invoice(request, order_id):
    # Fetch the ticket by ID
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    
    # Generate PDF for the selected ticket
    pdf = order.generate_pdf_invoice()
    # Create a BytesIO stream to hold the PDF data
    file_stream = io.BytesIO(pdf.output())

    # Create a FileResponse to send the PDF file
    response = FileResponse(file_stream, content_type='application/pdf', filename=f"order_invoice_{order_id}.pdf")
    
    return response

@login_required
@user_passes_test(is_admin_or_accountant_user)
def admin_confirm_order(request, order_id):
    if request.method != 'POST':
        return redirect('manage_orders')
    
    order = get_object_or_404(get_payment_model(), session_id=order_id)

    if order.status == PaymentStatus.CONFIRMED:
        order.is_confirmed = True
        order.save()

        for ticket in order.tickets.all():
            ticket.sold_as = SoldAsStatus.PRESALE_ONLINE
            ticket.save()
        
            ticket.queue_send_to_email()
            
        # Send confirmation and invoice email
        order.queue_confirmation_email()

    return redirect('manage_orders')

@login_required
@user_passes_test(is_admin_or_accountant_user)
def send_invoice(request, order_id):
    if request.method != 'POST':
        return redirect('manage_orders')
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    order.queue_payment_instructions_email()
    return redirect('manage_orders')

@login_required
@user_passes_test(is_admin_or_accountant_user)
def send_confirmation(request, order_id):
    if request.method != 'POST':
        return redirect('manage_orders')
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    
    if order.status != PaymentStatus.CONFIRMED:
        messages.error(request, _("Cannot resend confirmation email: order is not in CONFIRMED status. Current status: {status}").format(status=order.status))
    else:
        try:
            order.queue_confirmation_email()
            messages.success(request, _("Confirmation email queued successfully for {email}").format(email=order.billing_email))
        except Exception as e:
            messages.error(request, _("Failed to queue confirmation email: {error}").format(error=str(e)))
    
    return redirect('manage_orders')

@login_required
@user_passes_test(is_admin_or_accountant_user)
def send_refund_notification(request, order_id):
    if request.method != 'POST':
        return redirect('manage_orders')
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    
    if order.status != PaymentStatus.REFUNDED:
        messages.error(request, _("Cannot send refund notification: order is not in REFUNDED status. Current status: {status}").format(status=order.status))
    else:
        try:
            order.queue_refund_cancel_notification_email()
            messages.success(request, _("Refund notification email queued successfully for {email}").format(email=order.billing_email))
        except Exception as e:
            messages.error(request, _("Failed to queue refund notification email: {error}").format(error=str(e)))
    
    return redirect('manage_orders')

@login_required
@user_passes_test(is_admin_or_accountant_user)
def refund_order(request, order_id):
    if request.method != 'POST':
        return redirect('manage_orders')
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    
    if order.status != PaymentStatus.CONFIRMED:
        messages.error(request, _("Cannot refund order: order is not in CONFIRMED status. Current status: {status}").format(status=order.status))
    else:
        try:
            order.refund_or_cancel()
            messages.success(request, _("Order refunded successfully."))
        except Exception as e:
            messages.error(request, _("Failed to refund order: {error}").format(error=str(e)))
    
    return redirect('manage_orders')

@login_required
@user_passes_test(is_admin_or_accountant_user)
def cancel_order(request, order_id):
    if request.method != 'POST':
        return redirect('manage_orders')
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    
    can_cancel = (
        order.status == PaymentStatus.PREAUTH
        or (order.status == PaymentStatus.CONFIRMED and not order.is_confirmed)
    )

    if can_cancel:
        try:
            order.refund_or_cancel()
            messages.success(request, _("Order cancelled successfully."))
        except Exception as e:
            messages.error(request, _("Failed to cancel order: {error}").format(error=str(e)))
    else:
        messages.error(
            request,
            _(
                "Cannot cancel order: order must be in PREAUTH status or be an payment unconfirmed CONFIRMED order. "
                "Current status: {status}"
            ).format(status=order.status),
        )
    
    return redirect('manage_orders')

@login_required
@user_passes_test(is_admin_or_accountant_user)
def manage_orders(request):
    # show all orders that require manual confirmation
    # order must be set to PaymentStatus.CONFIRMED but is_confirmed must be False
    manual_orders = get_payment_model().objects.filter(status=PaymentStatus.CONFIRMED, is_confirmed=False)
    paid_orders = get_payment_model().objects.filter(status=PaymentStatus.CONFIRMED, is_confirmed=True)
    refunded_orders = get_payment_model().objects.filter(status=PaymentStatus.REFUNDED)
    all_orders = get_payment_model().objects.all()

    return TemplateResponse(request, 'manage_orders.html', {
        'manual_orders': manual_orders,
        'paid_orders': paid_orders,
        'all_orders': all_orders,
        'refunded_orders': refunded_orders,
        'currency': settings.DEFAULT_CURRENCY
    })

# create login page
def login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('event_list') 
    else:
        form = AuthenticationForm()
    return TemplateResponse(request, 'login.html', {'form': form})

def logout(request):
    # Log out the user
    auth_logout(request)
    return redirect('event_list')