from django.urls import path
from .views import (
    event_list,
    event_detail,
    event_check_in,
    handle_qr_result,
    toggle_ticket_activation,
    delete_ticket,
    update_ticket_email,
    send_ticket_email_view
)

urlpatterns = [
    path('', event_list, name='event_list'),  # Front page URL
    path('<uuid:event_id>/', event_detail, name='event_details'),  # Event detail URL
    path('<uuid:event_id>/check-in', event_check_in, name="event_check_in"),
    path('<uuid:event_id>/qr-result/', handle_qr_result, name="handle_qr_result"),
    path('toggle-ticket-activation/<uuid:ticket_id>/', toggle_ticket_activation, name='toggle_ticket_activation'),
    path('delete-ticket/<uuid:ticket_id>/', delete_ticket, name='delete_ticket'),  # Delete ticket URL
    path('update-ticket-email/<uuid:ticket_id>/', update_ticket_email, name='update_ticket_email'),  # Update ticket email URL
    path('send_ticket_email/<uuid:ticket_id>/', send_ticket_email_view, name='send_ticket_email'),
]