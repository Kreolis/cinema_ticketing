from django.urls import path
from .views import (
    event_list,
    qr_scanner,
    handle_qr_result
)

from tickets.views import ticket_selection

urlpatterns = [
    path('', event_list, name='event_list'),  # Front page URL
    path('<uuid:event_id>/', ticket_selection, name='ticket_selection'),
    path('<uuid:event_id>/qr-scanner', qr_scanner, name="qr_scanner"),
    path('<uuid:event_id>/qr-result', handle_qr_result, name="handle_qr_result"),
]