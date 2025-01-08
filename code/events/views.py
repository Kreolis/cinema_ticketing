from django.shortcuts import render, get_object_or_404
from django.views.generic import TemplateView
from django.http import JsonResponse

from .models import Event

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
def qr_scanner(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, 'qr_scanner.html', {
        'event': event,
    })

def handle_qr_result(request):
    if request.method == "POST":
        qr_code_data = request.POST.get('qr_code')
        # Process the QR code data
        return JsonResponse({"status": "success", "data": qr_code_data})
    return JsonResponse({"status": "error", "message": "Invalid request"})