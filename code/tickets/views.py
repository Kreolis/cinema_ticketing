from django.shortcuts import render, get_object_or_404, redirect
from django.template.response import TemplateResponse

# django-payments
from payments import get_payment_model, RedirectNeeded
from payments.models import PaymentStatus
from payments.forms import PaymentForm

from events.models import Event
from .models import Ticket

def ticket_selection(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    price_classes = event.price_classes.all()
    
    # Get the price classes for this event
    price_classes = event.price_classes.all()
    
    if request.method == 'POST':
        selected_tickets = []
        for price_class in price_classes:
            quantity = int(request.POST.get(f'quantity_{price_class.id}', 0))  # Get quantity from form
            if quantity > 0:
                for _ in range(quantity):
                    # Collect tickets for this price class
                    new_ticket = Ticket(
                            event=event,
                            price_class=price_class,
                            activated=False,
                        )
                    new_ticket.save()

                    selected_tickets.append(
                        new_ticket
                    )
        Payment = get_payment_model()
        payment = Payment.objects.create(
            #variant='default',  # this is the variant from PAYMENT_VARIANTS
            #status=PaymentStatus.WAITING,
        )

        # Add the selected tickets to the payment
        payment.selected_tickets.set(selected_tickets)
        total_amount = sum(ticket.price_class.price.amount for ticket in selected_tickets)  # Sum ticket prices
        payment.total = total_amount  # Set the precomputed total amount
        payment.save()

        # Redirect to payment or confirmation page
        return redirect('payment_create', payment_id=payment.id)

    return render(request, 'ticket_selection.html', {
        'event': event,
        'price_classes': price_classes,
    })



def payment_details(request, payment_id):
    payment = get_object_or_404(get_payment_model(), id=payment_id)

    try:
        form = payment.get_form(data=request.POST or None)
    except RedirectNeeded as redirect_to:
        return redirect(str(redirect_to))

    return TemplateResponse(
        request,
        'payment.html',
        {'form': form, 'payment': payment}
    )



def payment_create(request, payment_id):
    payment = get_object_or_404(get_payment_model(), id=payment_id)

    # Precompute the total amount from the associated tickets
    selected_tickets = payment.selected_tickets.all()  # Fetch all tickets linked to this payment
    total_amount = sum(ticket.price_class.price.amount for ticket in selected_tickets)  # Sum ticket prices
    payment.amount = total_amount  # Set the precomputed total amount
    payment.save()

    print(total_amount)
    print(payment.amount)
    
    """
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            # Save the payment instance and proceed with the payment gateway logic
            #payment = form.save(commit=False)
    """
            # Here, you would integrate with the payment gateway (Stripe, PayPal, etc.)
            # For example, for Stripe:
    """
    stripe_payment_intent = stripe.PaymentIntent.create(
        amount=int(payment.amount * 100),  # Convert to cents
        currency='usd',
        payment_method=request.POST['payment_method'],
        confirmation_method='manual',
        confirm=True
    )
    """

            # Update payment status in your model based on the gateway response
            #payment.status = 'confirmed'  # Assuming the payment was confirmed successfully
            #payment.save()
    """
            return redirect('payment_confirmation', payment_id=payment.id)
    else:
        form = PaymentForm()
    """
    form = PaymentForm()
    return render(request, 'create.html', {'form': form, 'payment': payment})

def payment_confirmation(request, payment_id):
    payment = get_object_or_404(get_payment_model(), id=payment_id)
    
    if payment.status == 'confirmed':
        # Mark the associated ticket as sold
        ticket = payment.order  # Assuming `order` is a Ticket
        #ticket.sold = True
        ticket.save()

        return render(request, 'payment/confirmation.html', {'payment': payment})
    else:
        return render(request, 'payment/failure.html', {'payment': payment})