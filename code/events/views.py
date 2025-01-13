from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms

from .models import Event, Ticket
from accounting.models import Order
from branding.models import Branding
from .forms import TicketSelectionForm

def event_list(request):
    # Retrieve all events, you can filter by start_time if needed
    events = Event.objects.all().order_by('start_time')  # Or use 'start_time' for upcoming events
    return render(request, 'event_list.html', {'events': events})

# Event detail view with ticket selection
def event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    price_classes = event.price_classes.all()
    
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
                        
            order, _ = Order.objects.get_or_create(session_id=request.session.session_key)
            order.update_tickets(selected_tickets)
            
    else:
        form = TicketSelectionForm(price_classes=price_classes)

    return render(request, 'event_details.html', {
        'event': event,
        'price_classes': price_classes,
        'form': form,
    })

# user ticket controls during order
def update_ticket_email(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if request.method == 'POST':
        new_email = request.POST.get('email')
        if new_email:
            ticket.email = new_email
            ticket.save()
            order = get_object_or_404(Order, session_id=request.session.session_key)
            return JsonResponse({"status": "success", "updated_email": ticket.email})
    return JsonResponse({"status": "error", "message": "Invalid request"})

def delete_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    order = get_object_or_404(Order, session_id=request.session.session_key)
    order.delete_ticket(ticket)
    return JsonResponse({"status": "success"})

def send_ticket_email_view(request, ticket_id):
    ticket = get_object_or_404(Ticket, pk=ticket_id)
    if ticket.email:
        ticket.send_to_email()
        return HttpResponse("Email sent successfully.")
    return HttpResponse("No email address provided.")


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

