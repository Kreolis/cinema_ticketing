from django.shortcuts import render
from django.views.generic import TemplateView

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