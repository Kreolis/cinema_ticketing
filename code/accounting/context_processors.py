from payments import get_payment_model


def cart_count(request):
    """
    Context processor to add the current order's ticket count to all templates.
    Returns 0 if there's no session or no order yet.
    """
    ticket_count = 0
    
    if request.session.session_key:
        try:
            order = get_payment_model().objects.get(session_id=request.session.session_key)
            ticket_count = order.tickets.count()
        except get_payment_model().DoesNotExist:
            ticket_count = 0
    
    return {'cart_ticket_count': ticket_count}
