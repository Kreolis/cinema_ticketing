from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse

import io

from django.conf import settings
from django.http import FileResponse

# django-payments
from payments import get_payment_model, RedirectNeeded
from payments.models import PaymentStatus

from .forms import PaymentInfoForm  # Add this import
from .forms import UpdateEmailsForm  # Add this import

from events.models import SoldAsStatus 

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
        order.delete()
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
        order.delete()
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

            order.session_id = request.session.session_key
            order.change_status(PaymentStatus.WAITING)

            # if the payment vairant is able to do a preauth, set the success and failure urls
            # check first if the name of the variant is matching with a variant that has the capture field set to False
            if settings.PAYMENT_VARIANTS[order.variant][1].get('capture', True) == False:
                order.failure_url = request.build_absolute_uri(reverse('payment_failed'))
                order.success_url = request.build_absolute_uri(reverse('order_payment', args=[order.session_id]))
            
            order.save()

            # update tickets so that they have an email address
            for ticket in order.tickets.all():
                if ticket.email == None:
                    ticket.email = order.billing_email
                    ticket.save()
            if settings.PAYMENT_VARIANTS[order.variant][1].get('capture', True) == False:
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
        'currency': settings.DEFAULT_CURRENCY})

def order_payment_overview(request):
    return order_payment(request, request.session.session_key)

def confirm_order(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    if order.status == PaymentStatus.PREAUTH:
        try:
            # make the payment with stripe
            # Capture the payment after review or fulfillment
            order.capture()

            order.change_status(PaymentStatus.CONFIRMED)
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
        return redirect('payment_form')
    return redirect('ticket_list', order_id=order_id)

def ticket_list(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)

    if order.status == PaymentStatus.INPUT:
        order.change_status(PaymentStatus.CONFIRMED)

        for ticket in order.tickets.all():
                ticket.sold_as = SoldAsStatus.PRESALE_ONLINE
                ticket.first_name = order.billing_first_name
                ticket.last_name = order.billing_last_name
                ticket.send_to_email()
                ticket.save()

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
        return render(request, 'ticket_list.html', {'order': order,
        'currency': settings.DEFAULT_CURRENCY})
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