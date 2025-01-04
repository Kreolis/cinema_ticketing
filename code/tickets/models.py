from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.signals import post_delete
from django.dispatch import receiver

from collections.abc import Iterable  # Correct import

from events.models import Ticket

from payments.models import BasePayment
from payments import PurchasedItem

class Payment(BasePayment):
    """
    Custom payment model that extends django-payments' BasePayment model
    """
    selected_tickets = models.ManyToManyField(Ticket)  # Tickets that are being purchased

    #def __str__(self):
    #    return f"Payment {self.id} for Order {self.order.id}"
    def get_failure_url(self) -> str:
        # Return a URL where users are redirected after
        # they fail to complete a payment:
        return 'payment/failure.html'

    def get_success_url(self) -> str:
        # Return a URL where users are redirected after
        # they successfully complete a payment:
        return 'payment/confirmation.html'

    def get_purchased_items(self) -> Iterable[PurchasedItem]:
        # Return items that will be included in this payment.
        for ticket in self.selected_tickets.all():
            # Assuming each ticket has a 'price_class' related to the price and other item details
            yield PurchasedItem(
                name=f"Ticket for {ticket.event.name}",  # Event name as part of the ticket name
                sku=f"TICKET-{ticket.id}",  # Unique SKU for each ticket
                quantity=1,  # Each ticket counts as one item
                price=ticket.price_class.price.amount,  # Price from the ticket's PriceClass
                currency=ticket.price_class.price.currency,  # Currency of the ticket
            )
    
@receiver(post_delete, sender=Payment)
def delete_related_tickets(sender, instance, **kwargs):
    """
    Delete all tickets associated with the payment when the payment is deleted.
    """
    # Delete all related tickets
    instance.selected_tickets.all().delete()