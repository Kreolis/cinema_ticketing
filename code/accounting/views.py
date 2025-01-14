from django.shortcuts import render, get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.http import FileResponse

import io

from django.conf import settings

# django-payments
from payments import get_payment_model, RedirectNeeded
from payments.models import PaymentStatus
from payments.forms import PaymentForm

from .models import Order
from .forms import PaymentInfoForm  # Add this import
from .forms import UpdateEmailsForm  # Add this import

def cart_view(request):
    order, _ = Order.objects.get_or_create(session_id=request.session.session_key)

    if order.status == PaymentStatus.CONFIRMED:
        # this is an old order that has already been paid
        # create a new session and order
        request.session.cycle_key()
        order, _ = Order.objects.get_or_create(session_id=request.session.session_key)

    elif not order.is_valid():
        # this is an old order that has expired
        # delete the order and create a new one
        order.delete()
        order, _ = Order.objects.get_or_create(session_id=request.session.session_key)

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
    return render(request, 'cart.html', {'form': form, 'order': order, 'time_remaining': time_remaining})

def payment_form(request):
    order = get_object_or_404(Order, session_id=request.session.session_key)
    if not order.is_valid():
        order.delete()
        order = Order.objects.create(session_id=request.session.session_key)
    if request.method == 'POST':
        form = PaymentInfoForm(request.POST)
        
        if form.is_valid():
            payment = form.save(commit=False)
            payment.save()
            order.update_payment(payment)

            # Set payment attributes
            payment.variant = 'default'
            payment.total = order.total.amount
            payment.currency = settings.DEFAULT_CURRENCY

            payment.save()  # Save the payment object

            # update tickets so that they have an email address
            for ticket in order.tickets.all():
                if ticket.email == None:
                    ticket.email = payment.billing_email
                    ticket.save()

            return redirect('order_payment_overview')  # Redirect to the overview page
    else:
        form = PaymentInfoForm(instance=order.payment)

    time_remaining = order.get_remaining_time()
    return render(request, 'payment_form.html', {'form': form, 'order': order, 'time_remaining': time_remaining})

def order_payment_overview(request):
    order = get_object_or_404(Order, session_id=request.session.session_key)

    time_remaining = order.get_remaining_time()
    return render(request, 'order_payment_overview.html', {'order': order, 'time_remaining': time_remaining})


def payment_process(request, payment_id):
    order = get_object_or_404(Order, session_id=request.session.session_key)
    payment = order.payment
    if payment.status == PaymentStatus.WAITING:
        form = PaymentForm(data=request.POST or None, payment=payment)
        if form.is_valid():
            form.save()
            return redirect('order_payment_overview')
    return TemplateResponse(request, 'payment_process.html', {'form': form, 'payment': payment})

def confirm_order(request):
    order = get_object_or_404(Order, session_id=request.session.session_key)
    #payment = get_object_or_404(get_payment_model(), order=order)
    payment = order.payment
    if payment.status == PaymentStatus.WAITING:
        try:
            payment.change_status(PaymentStatus.CONFIRMED)
            order.status = PaymentStatus.CONFIRMED
            order.save()

            for ticket in order.tickets.all():
                ticket.send_to_email()
            
            # Send confirmation and invoice email
            order.send_confirmation_email()
            
            # order is paid
            # make sure the user can make a new order by creating a new session
            request.session.cycle_key()
            
        except RedirectNeeded as e:
            return e.response
    return redirect('ticket_list', order_id=order.session_id)

def ticket_list(request, order_id):
    order = get_object_or_404(Order, session_id=order_id)
    if order.payment.status == PaymentStatus.CONFIRMED:
        return render(request, 'ticket_list.html', {'order': order})
    else:
        return redirect('payment_form')
    

def show_generated_invoice(request, order_id):
    # Fetch the ticket by ID
    order = get_object_or_404(Order, session_id=order_id)
    
    # Generate PDF for the selected ticket
    pdf = order.generate_pdf_invoice()
    # Create a BytesIO stream to hold the PDF data
    file_stream = io.BytesIO(pdf.output())

    # Create a FileResponse to send the PDF file
    response = FileResponse(file_stream, content_type='application/pdf', filename="order_invoice_{order_id}.pdf")
    
    return response