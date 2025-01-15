from django.shortcuts import render, get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.http import FileResponse, JsonResponse

import io

from django.conf import settings

# django-payments
from payments import get_payment_model, RedirectNeeded
from payments.models import PaymentStatus
from payments.forms import PaymentForm

from .forms import PaymentInfoForm  # Add this import
from .forms import UpdateEmailsForm  # Add this import

def cart_view(request):
    if not request.session.session_key:
        request.session.create()

    order, _ = get_payment_model().objects.get_or_create(session_id=request.session.session_key)

    if order.status == PaymentStatus.CONFIRMED:
        # this is an old order that has already been paid
        # create a new session and order
        request.session.cycle_key()
        order, _ = get_payment_model().objects.get_or_create(session_id=request.session.session_key)

    elif not order.is_valid():
        # this is an old order that has expired
        # delete the order and create a new one
        order.delete()
        order, _ = get_payment_model().objects.get_or_create(session_id=request.session.session_key)

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
    order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
    order.reset_timeout()

    if not order.is_valid():
        order.delete()
        order = get_payment_model().objects.create(session_id=request.session.session_key)
        return redirect('cart_view')
        
    if request.method == 'POST':
        form = PaymentInfoForm(request.POST)
        
        if form.is_valid():
            order = form.save(commit=False)
            order.session_id = request.session.session_key
            order.status = PaymentStatus.WAITING
            order.save()

            # update tickets so that they have an email address
            for ticket in order.tickets.all():
                if ticket.email == None:
                    ticket.email = order.billing_email
                    ticket.save()
            
            try:
                gateway_form =  order.get_form(request)
            except RedirectNeeded as e:
                return e.response
            
            return redirect('order_payment_overview')  # Redirect to the overview page
    else:
        form = PaymentInfoForm(instance=order)

    time_remaining = order.get_remaining_time()
    return render(request, 'payment_form.html', 
                  {'form': form, 
                   'order': order, 
                   'time_remaining': time_remaining, 
                   'stripe_public_key': settings.STRIPE_PUBLIC_KEY,
                   'currency': settings.DEFAULT_CURRENCY
                })

def order_payment_overview(request):
    order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
    order.reset_timeout()

    time_remaining = order.get_remaining_time()
    return render(request, 'order_payment_overview.html', {'order': order, 'time_remaining': time_remaining,
        'currency': settings.DEFAULT_CURRENCY})


def payment_process(request):
    order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
    if order.status == PaymentStatus.WAITING:
        form = PaymentForm(data=request.POST or None, payment=order)
        if form.is_valid():
            form.save()
            return redirect('order_payment_overview')
    return TemplateResponse(request, 'payment_process.html', {'form': form, 'payment': order,
        'currency': settings.DEFAULT_CURRENCY})

def confirm_order(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    if order.status == PaymentStatus.PREAUTH:
        try:
            # make the payment with stripe
            # Capture the payment after review or fulfillment
            #payment.capture()

            order.change_status(PaymentStatus.CONFIRMED)
            order.status = PaymentStatus.CONFIRMED
            order.save()

            for ticket in order.tickets.all():
                ticket.sold = True
                ticket.send_to_email()
            
            # Send confirmation and invoice email
            order.send_confirmation_email()
            
            # order is paid
            # make sure the user can make a new order by creating a new session
            request.session.cycle_key()
            
        except RedirectNeeded as e:
            return e.response
    else:
        return redirect('payment_form')
    return redirect('ticket_list', order_id=order_id)

def ticket_list(request, order_id):
    order = get_object_or_404(get_payment_model(), session_id=order_id)
    print("halllo here is the ticket list")
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
    response = FileResponse(file_stream, content_type='application/pdf', filename="order_invoice_{order_id}.pdf")
    
    return response