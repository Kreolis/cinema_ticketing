from django.db import models
from django.utils import timezone
from datetime import timedelta

from djmoney.models.fields import MoneyField

from events.models import Ticket
from branding.models import get_active_branding

from payments.models import BasePayment, PaymentStatus
from payments import PurchasedItem
from django.contrib import messages
from django.conf import settings

class Payment(BasePayment):
    """
    Custom payment model that extends django-payments' BasePayment model
    """

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

    def get_purchased_items(self) -> str:
        # Return items that will be included in this payment.
        return None
    
    def __str__(self):
        return f"Payment {self.id}"

# class for holding one sessions order until payment is completed
class Order(models.Model):
    session_id = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now_add=True)
    tickets = models.ManyToManyField(Ticket, related_name="Tickets")
    total = MoneyField(max_digits=14, decimal_places=2, default=0.0)
    timeout = models.IntegerField(default=10)  # in minutes

    # set to branding order_timeout if available
    if get_active_branding() and get_active_branding().order_timeout:
        timeout = get_active_branding().order_timeout

    #status based on PaymentStatus
    status = models.CharField(
        max_length=10,
        choices=PaymentStatus.CHOICES,
        default=PaymentStatus.WAITING,
    )

    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, default=None, null=True)

    def __str__(self):
        return f"Order {self.id} for session {self.session_id}"

    def is_valid(self) -> bool:
        if self.updated is None:
            return False
        if self.status == PaymentStatus.CONFIRMED:
            return True
        return timezone.now() - self.updated <= timedelta(minutes=self.timeout)

    def save(self, *args, **kwargs):
        if not self.pk and Order.objects.filter(session_id=self.session_id).exists():
            # order for this session already exists
            # return existing order instead of creating a new one
            existing_order = Order.objects.get(session_id=self.session_id)
            return existing_order
        
        super().save(*args, **kwargs)

    def update_tickets(self, new_tickets):
        # add new tickets to order
        self.tickets.add(*new_tickets)
        # calculate new total amount
        self.total = sum(ticket.price_class.price for ticket in self.tickets.all())  # Sum ticket prices
        self.updated = timezone.now()
        self.save()
    
    def delete_ticket(self, ticket):
        # remove ticket from order
        self.tickets.remove(ticket)
        # delete ticket
        ticket.delete()
        # calculate new total amount
        self.total = sum(ticket.price_class.price for ticket in self.tickets.all())  # Sum ticket prices
        self.updated = timezone.now()
        self.save()

    def update_payment(self, new_payment):
        """
        Update the payment associated with this order.
        """
        if self.payment:
            self.payment.delete() # delete old payment
        self.payment = new_payment
        self.updated = timezone.now()
        self.save()

    def get_remaining_time(self):
        return self.timeout - (timezone.now() - self.updated).seconds // 60

    # delete order and associated tickets
    def delete(self, *args, **kwargs):
        if self.status == PaymentStatus.CONFIRMED:
            if settings.CONFIRM_DELETE_PAID_ORDER:
                messages.warning(None, "Cannot delete a paid order.")
                return None
            else:
                messages.warning(None, "You are about to delete a paid order. All associated tickets will also be deleted.")
        
        self.tickets.all().delete()
        self.payment.delete()   
        super().delete(*args, **kwargs)


