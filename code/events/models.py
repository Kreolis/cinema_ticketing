from django.db import models
from djmoney.models.fields import MoneyField
import uuid

class Location(models.Model):
    """
    Global location model for events.
    """
    name = models.CharField(max_length=255, unique=True)
    total_seats = models.PositiveIntegerField()
    
    # address fields
    street = models.CharField(("street"), max_length=128, default="Musterstraße")
    house_number = models.IntegerField(("house number"), default=0)
    city = models.CharField(("city"), max_length=64, default="Landshut")
    zip_code = models.CharField(("zip code"), max_length=5, default="84028")

    def __str__(self):
        return self.name

class PriceClass(models.Model):
    """
    Global price class model for events.
    """
    name = models.CharField(max_length=100)  # e.g., VIP, Regular
    price = MoneyField(max_digits=14, decimal_places=2, default_currency='EUR')

    def __str__(self):
        return f"{self.name}"

class Ticket(models.Model):
    """
    Global ticket model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # ticket id

    price_class = models.ForeignKey(PriceClass, on_delete=models.CASCADE)  # Reference to PriceClass (ticket price)
    event = models.ForeignKey("Event", on_delete=models.CASCADE)  # Add event to ticket
    seat = models.IntegerField(unique=True) # seat number
    sold = models.BooleanField(default=False)  # Track if ticket is sold

    # ticket activation
    activated = models.BooleanField(default=False)  # ticket is activated
    
    def save(self, *args, **kwargs):
        # Automatically assign the next available seat number for this event
        if not self.seat:
            last_ticket = Ticket.objects.filter(event=self.event).order_by('seat').last()
            self.seat = last_ticket.seat + 1 if last_ticket else 1  # Start with seat 1 if no tickets exist
        super().save(*args, **kwargs)  # Call the superclass save method
        
    def __str__(self):
        return str(self.id)
    
class Event(models.Model):
    """
    Global event model.
    """
    name = models.CharField(max_length=255, unique=True) # name of event, needs to be unique
    start_time = models.DateTimeField() # start time of event
    duration = models.DurationField(default='02:00:00')  # 2 hours
    location = models.ForeignKey(Location, on_delete=models.CASCADE) # add location to event
    price_classes = models.ManyToManyField(PriceClass, related_name="events")  # multiple PriceClasses for an event
    program_link = models.URLField(blank=True, null=True) # link to website with program

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # event id
    
    # Optional field to customize the number of seats for this event
    custom_seats = models.PositiveIntegerField(null=True, blank=True)  # If None, use total_seats from location

    def __str__(self):
        return self.name

    @property
    def available_seats(self):
        """
        Return the number of seats available for this event.
        If custom_seats is set, use that; otherwise, fallback to the location's total_seats.
        """
        total_seats = self.custom_seats if self.custom_seats is not None else self.location.total_seats
        sold_tickets = self.ticket_set.filter(sold=True).count()  # Count sold tickets for the event
        return total_seats - sold_tickets  # Subtract sold tickets from total seats

    @property
    def sold_tickets_count(self):
        """
        Return the number of tickets that have been sold for this event.
        """
        return self.ticket_set.filter(sold=True).count()

    @property
    def total_seats(self):
        """
        Return the total number of seats available for the event (either from the location or customized).
        """
        return self.custom_seats if self.custom_seats is not None else self.location.total_seats
    