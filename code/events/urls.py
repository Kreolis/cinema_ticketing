from django.urls import path
from .views import (
    event_list,
    event_check_in,
    handle_qr_result
)

from tickets.views import ticket_selection

urlpatterns = [
    path('', event_list, name='event_list'),  # Front page URL
    path('<uuid:event_id>/', ticket_selection, name='Event Detail'),  # Event detail URL
    path('<uuid:event_id>/check-in', event_check_in, name="Event Check In"),
    path('<uuid:event_id>/qr-result', handle_qr_result, name="handle_qr_result"),
]