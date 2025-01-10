from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.decorators import login_required, user_passes_test

from .models import Event
from .models import Ticket

def event_list(request):
    # Retrieve all events, you can filter by start_time if needed
    events = Event.objects.all().order_by('start_time')  # Or use 'start_time' for upcoming events
    return render(request, 'event_list.html', {'events': events})

class EventLandingPageView(TemplateView):
    template_name = "landing.html"
 
    def get_context_data(self, **kwargs):
        product = Event.objects.get(name="Test Product")
        prices = Event.price_classes.objects.filter(event=product)
        context = super(EventLandingPageView,
                        self).get_context_data(**kwargs)
        context.update({
            "product": product,
            "prices": prices
        })
        return context
    

# ticket scanning
def user_in_ticket_managers_group_or_admin(user):
    return user.groups.filter(name='admin_user_group').exists() or user.groups.filter(name='ticket_managers_group').exists() or user.is_superuser

@login_required
@user_passes_test(user_in_ticket_managers_group_or_admin)
def event_check_in(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    tickets = Ticket.objects.filter(event=event)
    return render(request, 'check_in.html', {
        'event': event,
        'tickets': tickets,
    })

@login_required
@user_passes_test(user_in_ticket_managers_group_or_admin)
def handle_qr_result(request):
    if request.method == "POST":
        qr_code_data = request.POST.get('qr_code')
        # Process the QR code data
        return JsonResponse({"status": "success", "data": qr_code_data})
    return JsonResponse({"status": "error", "message": "Invalid request"})