from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.conf import settings

import io

from payments import get_payment_model

from .models import Event, Ticket
from branding.models import Branding
from .forms import TicketSelectionForm

def event_list(request):
    # Retrieve all events, you can filter by start_time if needed
    events = Event.objects.all().order_by('start_time')  # Or use 'start_time' for upcoming events
    return render(request, 'event_list.html', 
                  {'events': events,
                   'currency': settings.DEFAULT_CURRENCY
                   })

# Event detail view with ticket selection
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    price_classes = event.price_classes.all()
    
    # Ensure the session is created
    if not request.session.session_key:
        request.session.create()

    if request.method == 'POST':
        form = TicketSelectionForm(request.POST, price_classes=price_classes)
        if form.is_valid():
            selected_tickets = []
            for price_class in price_classes:
                quantity = form.cleaned_data.get(f'quantity_{price_class.id}', 0)
                if quantity > 0:
                    for _ in range(quantity):
                        new_ticket = Ticket(
                            event=event,
                            price_class=price_class,
                            activated=False,
                        )
                        new_ticket.save()
                        selected_tickets.append(new_ticket)
                        
            order, _ = get_payment_model().objects.get_or_create(session_id=request.session.session_key)
            order.update_tickets(selected_tickets)
            
    else:
        form = TicketSelectionForm(price_classes=price_classes)

    show_button = user_in_ticket_managers_group_or_admin(request.user)

    return render(request, 'event_details.html', {
        'event': event,
        'price_classes': price_classes,
        'form': form,
        'show_button': show_button,
        'currency': settings.DEFAULT_CURRENCY
    })

# user ticket controls during order
def update_ticket_email(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        new_email = request.POST.get('email')
        if new_email:
            ticket.email = new_email
            ticket.save()
            order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
            return JsonResponse({"status": "success", "updated_email": ticket.email})
    return JsonResponse({"status": "error", "message": "Invalid request"})

def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    order = get_object_or_404(get_payment_model(), session_id=request.session.session_key)
    order.delete_ticket(ticket)
    return JsonResponse({"status": "success"})

def show_generated_ticket_pdf(request, ticket_id):
    # Fetch the ticket by ID
    ticket = Ticket.objects.get(pk=ticket_id)
    
    # Generate PDF for the selected ticket
    pdf = ticket.generate_pdf_ticket()
    # Create a BytesIO stream to hold the PDF data
    file_stream = io.BytesIO(pdf.output())

    # Create a FileResponse to send the PDF file
    response = FileResponse(file_stream, content_type='application/pdf', filename=f"ticket_{ticket.id}.pdf")
    
    return response

def send_ticket_email(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if ticket.email:
        ticket.send_to_email()
        return JsonResponse({"status": "success", "message": "Email sent to " + ticket.email})
    return JsonResponse({"status": "error", "message": "No email address provided."})


# ticket scanning
def user_in_ticket_managers_group_or_admin(user):
    return user.groups.filter(name='admin_user_group').exists() or user.groups.filter(name='ticket_managers_group').exists() or user.is_superuser

@login_required
@user_passes_test(user_in_ticket_managers_group_or_admin)
def event_check_in(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    tickets = Ticket.objects.filter(event=event)
    branding = Branding.objects.filter(is_active=True).first()
    return render(request, 'check_in.html', {
        'event': event,
        'tickets': tickets,
        'branding': branding,
        'currency': settings.DEFAULT_CURRENCY
    })

@login_required
@user_passes_test(user_in_ticket_managers_group_or_admin)
def handle_qr_result(request, event_id):
    if request.method == "POST":
        qr_code_data = request.POST.get('qr_code')
        try:
            ticket = Ticket.objects.get(id=qr_code_data, event_id=event_id)
            if ticket.activated:
                return JsonResponse({"status": "error", "message": "Ticket already activated"})
            ticket.activated = True
            ticket.save()
            return JsonResponse({"status": "success", "activated": ticket.activated, "ticket_id": str(ticket.id)})
        except Ticket.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Ticket not found"})
    return JsonResponse({"status": "error", "message": "Invalid request"})

@login_required
@user_passes_test(user_in_ticket_managers_group_or_admin)
def toggle_ticket_activation(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    ticket.activated = not ticket.activated
    ticket.save()
    return JsonResponse({"status": "success", "activated": ticket.activated})

