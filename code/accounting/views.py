from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login 
from django.contrib.auth import logout as auth_logout 

import io

from django.conf import settings
from django.http import FileResponse

# django-payments
from payments import get_payment_model, RedirectNeeded
from payments.models import PaymentStatus

from .forms import PaymentInfoForm
from .forms import UpdateEmailsForm 

from events.models import SoldAsStatus
from events.views import user_in_ticket_managers_group_or_admin

def cart_view(request):
    if not request.session.session_key:
        request.session.create()

    order, _ = get_payment_model().objects.get_or_create(session_id=request.session.session_key)

    if order.status == PaymentStatus.CONFIRMED:
        # this is an old order that has already been paid
        # create a new session and order
        request.session.cycle_key()
        order = get_payment_model().objects.get_or_create(session_id=request.session.session_key)

    elif not order.is_valid():
        # this is an old order that has expired
        # delete the order and create a new one
        order.delete(request)
        order = get_payment_model().objects.create(session_id=request.session.session_key)

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
    return render(request, 'cart.html', {'form': form, 'order': order, 'time_remaining': time_remaining,
        'currency': settings.DEFAULT_CURRENCY})

def payment_form(request):
    try:
        order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
    except:
        return redirect('cart_view')
        
    if not order.is_valid():
        order.delete(request)
        order = get_payment_model().objects.create(session_id=request.session.session_key)
        return redirect('cart_view')
        
    gateway_form = None  # Initialize gateway_form to None
    
    if request.method == 'POST':
        order.reset_timeout()
        form = PaymentInfoForm(request.POST)
        
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

            # enable user to choose payment method
            order.variant = form_fields["payment_method"]

            # set the session_id to the current session
            order.session_id = request.session.session_key
            order.change_status(PaymentStatus.WAITING)

            # if the payment vairant is able to do a preauth, set the success and failure urls
            # check first if the name of the variant is matching with a variant that has the capture field set to False
            if settings.PAYMENT_VARIANTS[order.variant][1].get('capture') == False:
                order.failure_url = request.build_absolute_uri(reverse('payment_failed'))
                order.success_url = request.build_absolute_uri(reverse('order_payment', args=[order.session_id]))
            
            order.save()

            # update tickets so that they have an email address
            for ticket in order.tickets.all():
                if ticket.email == None:
                    ticket.email = order.billing_email
                    ticket.save()
            
            if settings.PAYMENT_VARIANTS[order.variant][1].get('capture') == False:
                try:
                    order.change_status(PaymentStatus.PREAUTH)
                    gateway_form = order.get_form(request)
                except RedirectNeeded as e:
                    return redirect(str(e))
            
            return redirect('order_payment_overview')
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
                'payment_method': order.variant
            })
        else:
            form = PaymentInfoForm()

    time_remaining = order.get_remaining_time()
    return render(request, 'payment_form.html', 
                  {'form': form,
                   'gateway_form': gateway_form,
                   'order': order, 
                   'time_remaining': time_remaining, 
                   'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
                   'currency': settings.DEFAULT_CURRENCY
                })

def payment_failed(request):
    return render(request, 'payment_failed.html')

def order_payment(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    order.reset_timeout()
    
    time_remaining = order.get_remaining_time()
    return render(request, 'order_payment_overview.html', {'order': order, 'time_remaining': time_remaining,
        'currency': settings.DEFAULT_CURRENCY, 'humanzied_payment_variant': settings.HUMANIZED_PAYMENT_VARIANT[order.variant]})

def order_payment_overview(request):
    return order_payment(request, request.session.session_key)

def confirm_order(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)

    if order.status == PaymentStatus.PREAUTH:
        # variant was preauthed therefore capture the payment
        try:
            # Capture the payment after review or fulfillment
            order.capture()

            order.change_status(PaymentStatus.CONFIRMED)
            order.is_confirmed = True
            order.save()

            for ticket in order.tickets.all():
                ticket.sold_as = SoldAsStatus.PRESALE_ONLINE
                ticket.first_name = order.billing_first_name
                ticket.last_name = order.billing_last_name
                ticket.send_to_email()
                ticket.save()
            
            # Send confirmation and invoice email
            order.send_confirmation_email()
            
            # order is paid
            # make sure the user can make a new order by creating a new session
            request.session.cycle_key()
            
        except RedirectNeeded as e:
            return e.response
        
    elif order.status == PaymentStatus.WAITING:

        if not order.variant == 'advance_payment':
            # variant was not preauthed therefore initiate the payment
            order.failure_url = request.build_absolute_uri(reverse('payment_failed'))
            order.success_url = request.build_absolute_uri(reverse('ticket_list', args=[order_id]))
        
            order.save()

            try:
                order.change_status(PaymentStatus.INPUT)
                gateway_form = order.get_form(request)
            except RedirectNeeded as e:
                return redirect(str(e))
        else:
            # variant was advance payment therefore confirm the order
            order.change_status(PaymentStatus.CONFIRMED)
            order.save()

            for ticket in order.tickets.all():
                ticket.sold_as = SoldAsStatus.PRESALE_ONLINE_WAITING
                ticket.first_name = order.billing_first_name
                ticket.last_name = order.billing_last_name
                ticket.save()

            if not order.is_confirmed:
                # Send payment instructions email
                order.send_payment_instructions_email()
            else:
                # Send confirmation and invoice email
                order.send_confirmation_email()
            
            # order is reserved
            # make sure the user can make a new order by creating a new session
            request.session.cycle_key()
    else:
        return redirect('payment_form')
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
                if order.is_confirmed:
                    ticket.send_to_email()
                ticket.save()

        if not order.is_confirmed:
            # Send payment instructions email
            order.send_payment_instructions_email()
        else:
            # Send confirmation and invoice email
            order.send_confirmation_email()

        if request.session.session_key == None:
            print(f"Session key: {request.session.session_key}")
            print("No session key found. Cycle key.")
            request.session.create()
        

        # order is paid
        # make sure the user can make a new order by creating a new session
        while request.session.session_key == order_id:
            print(f"Session key: {request.session.session_key}")
            print("Session key is the same as order ID. Cycle key.")
            request.session.cycle_key()

        print(f"Session key: {request.session.session_key}")

    # if order is payed show the tickets
    if order.status == PaymentStatus.CONFIRMED:
        return render(request, 'ticket_list.html', {
            'order': order,
            'currency': settings.DEFAULT_CURRENCY,
            'payment_instructions': order.get_payment_instructions(),
            'humanzied_payment_variant': settings.HUMANIZED_PAYMENT_VARIANT[order.variant]
        })
    else:
        return redirect('payment_form')
    

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
@user_passes_test(user_in_ticket_managers_group_or_admin)
def admin_confirm_order(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)

    if order.status == PaymentStatus.CONFIRMED:
        order.is_confirmed = True
        order.save()

        for ticket in order.tickets.all():
            ticket.sold_as = SoldAsStatus.PRESALE_ONLINE
            ticket.save()
        
            ticket.send_to_email()
            
        # Send confirmation and invoice email
        order.send_confirmation_email()

    return redirect('manage_orders')

@login_required
@user_passes_test(user_in_ticket_managers_group_or_admin)
def manage_orders(request):
    # show all orders that require manual confirmation
    # order must be set to PaymentStatus.CONFIRMED but is_confirmed must be False
    manual_orders = get_payment_model().objects.filter(status=PaymentStatus.CONFIRMED, is_confirmed=False)
    paid_orders = get_payment_model().objects.filter(status=PaymentStatus.CONFIRMED, is_confirmed=True)

    all_orders = get_payment_model().objects.all()

    return render(request, 'manage_orders.html', {
        'manual_orders': manual_orders,
        'paid_orders': paid_orders,
        'all_orders': all_orders,
        'currency': settings.DEFAULT_CURRENCY
    })

# Example of how to run the management command periodically using Celery
from celery import shared_task
from django.core.management import call_command

@shared_task
def delete_timed_out_orders():
    call_command('delete_timed_out_orders')

# Schedule the task in your Celery beat schedule
# In your Celery configuration file (e.g., celery.py or settings.py)
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'delete-timed-out-orders-every-10-minutes': {
        'task': 'accounting.views.delete_timed_out_orders',
        'schedule': crontab(minute='*/10'),  # Adjust the schedule as needed
    },
}

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
    return render(request, 'login.html', {'form': form})

def logout(request):
    # Log out the user
    auth_logout(request)
    return redirect('event_list')