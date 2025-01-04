from django.urls import path
from .views import (
    event_list,
)

from tickets.views import ticket_selection

urlpatterns = [
    path('', event_list, name='event_list'),  # Front page URL
    path('<uuid:event_id>/', ticket_selection, name='ticket_selection'),
]