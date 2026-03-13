from django.db import models, transaction
from django.conf import settings

from django.core.mail import EmailMessage
from django.utils.translation import gettext_lazy as _
import django.utils.timezone
from pytz import common_timezones, timezone as pytz_timezone

from datetime import datetime, timedelta, timezone

from fpdf import FPDF
import qrcode
import os
import tempfile
import uuid

import logging

logger = logging.getLogger(__name__)

from branding.models import get_active_branding

BOOTSTRAP_COLORS = [
    ("#0d6efd", _("Blue")),
    ("#6c757d", _("Gray")),
    ("#198754", _("Green")),
    ("#dc3545", _("Red")),
    ("#ffc107", _("Warning")),
    ("#0dcaf0", _("Cyan")),
    ("#d63384", _("Pink")),
    ("#fd7e14", _("Orange")),
    ("#6610f2", _("Indigo")),
    ("custom", _("Custom Color")),
]
class SoldAsStatus:
    WAITING = "waiting"
    PRESALE_ONLINE = "presale_online"
    PRESALE_ONLINE_WAITING = "presale_online_waiting"
    PRESALE_DOOR = "presale_door"
    DOOR = "door"

    CHOICES = [
        (WAITING, _("Ticket not yet sold")),
        (PRESALE_ONLINE, _("Ticket was sold in online presale")),
        (PRESALE_ONLINE_WAITING, _("Ticket was sold in online presale, but not yet confirmed")),
        (PRESALE_DOOR, _("Ticket was sold in door presale")),
        (DOOR, _("Ticket was sold at the door")),
    ]

class Location(models.Model):
    """
    Global location model for events.
    """
    name = models.CharField(_("name"), max_length=255, unique=True)
    total_seats = models.PositiveIntegerField(_("total seats"))
    
    # address fields
    street = models.CharField(_("street"), max_length=128, default="Musterstraße")
    house_number = models.IntegerField(_("house number"), default=0)
    city = models.CharField(_("city"), max_length=64, default="Landshut")
    zip_code = models.CharField(_("zip code"), max_length=5, default="84028")
    
    displayed_color = models.CharField(
        _("displayed color"),
        max_length=7,
        default=BOOTSTRAP_COLORS[0][0],
        choices=BOOTSTRAP_COLORS,
        help_text=_("Selected the color for the card view of all events at this location. A custom color for each event can be selected in the event. If 'Custom Color' is selected, enter a hex color code in the 'Custom Color' field.")
    )
    custom_color = models.CharField(
        _("custom color"),
        max_length=7,
        blank=True,
        null=True,
        help_text=_("Hex color code if 'Custom Color' is selected (e.g., #007bff)")
    )

    def __str__(self):
        return self.name
    
    def get_address(self):
        return f"{self.street} {self.house_number}, {self.zip_code} {self.city}"
    
    def get_color(self):
        """Return the color to use - either custom_color or displayed_color"""
        if self.displayed_color == "custom":
            if self.custom_color:
                return self.custom_color
            # Fallback to default color if custom is selected but no custom_color is set
            return BOOTSTRAP_COLORS[0][0]  # Default blue color
        return self.displayed_color
    
    def get_color_rgb(self):
        """Convert hex color to RGB tuple as string (e.g., '13, 202, 240')"""
        color = self.get_color()
        # Remove # if present
        color = color.lstrip('#')
        # Convert hex to RGB
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        return f"{r}, {g}, {b}"

class PriceClass(models.Model):
    """
    Global price class model for events.
    """
    name = models.CharField(_("name"), max_length=100)  # e.g., VIP, Regular
    price =  models.DecimalField(max_digits=9, decimal_places=2, default="0.0", help_text=_(f"Price in {settings.DEFAULT_CURRENCY}"))  # Price for the ticket
    notification_message = models.TextField(_("notification message"), blank=True, null=True)  # Optional message to display to the user

    # optional field to make secret price classes, only shown to staff/door selling
    secret = models.BooleanField(_("secret"), default=False)

    def __str__(self):
        return f"{self.name} - {self.price} {settings.DEFAULT_CURRENCY}"

class Ticket(models.Model):
    """
    Global ticket model.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # ticket id

    price_class = models.ForeignKey(PriceClass, verbose_name=_("price class"), on_delete=models.CASCADE)  # Reference to PriceClass (ticket price)
    event = models.ForeignKey("Event", verbose_name=_("event"), on_delete=models.CASCADE)  # Add event to ticket
    seat = models.IntegerField(_("seat number")) # seat number
    sold_as = models.CharField(_("sold as"), max_length=24, choices=SoldAsStatus.CHOICES, default=SoldAsStatus.WAITING)  # How the ticket was sold

    first_name = models.CharField(_("first name"), max_length=128, blank=True, null=True)  # First name of the ticket holder/buyer
    last_name = models.CharField(_("last name"), max_length=128, blank=True, null=True)  # Last name of the ticket holder/buyer

    email = models.EmailField(_("email"), blank=True, null=True)  # Email address of the ticket holder

    # ticket activation
    activated = models.BooleanField(_("activated"), default=False)  # ticket is activated
    
    def save(self, *args, **kwargs):
        # Automatically assign the next available seat number for this event
        if not self.seat:
            last_ticket = Ticket.objects.filter(event=self.event).order_by('seat').last()
            self.seat = last_ticket.seat + 1 if last_ticket else 1  # Start with seat 1 if no tickets exist
        super().save(*args, **kwargs)  # Call the superclass save method
        
    def __str__(self):
        return str(self.id) + " - " + str(self.event) + " - " + str(self.seat)

    def generate_pdf_ticket(self):
        """
        Generate a PDF ticket for the given Ticket instance.
        """
        # Create a QR code from the ticket ID
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(self.id)
        qr.make(fit=True)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            qr_image_path = temp_file.name
            qr_image = qr.make_image(fill_color="black", back_color="white")
            qr_image.save(qr_image_path)

        try:
            # Create the PDF
            pdf = FPDF(unit="cm", format=(21.0, 8.5))  # Standard event ticket size
            pdf.set_margins(0.5, 0.5)  # Set margins 
            pdf.set_auto_page_break(auto=True, margin=0.2)  # Enable auto page break with a margin of 0.2 cm
            # Set font for the PDF
            font = "Helvetica"  # Default font
            pdf.set_font(font)

            # If a template is provided, use it as the canvas
            if self.event.ticket_background:
                try:
                    pdf.set_page_background(self.event.ticket_background)
                except Exception as e:
                    logger.error(f"Error loading template image: {e}")
            
            pdf.add_page()
            borders = 0
            
            # Add Event Title
            pdf.set_font(font, size=18, style='B')
            pdf.cell(14, 0.65, text=f"{self.event.name}", border=borders, align='L')
            
            # Add Ticket Details in a Layout
            pdf.set_font(font, size=15)
            pdf.ln(1.25)  # Move to the next line

            pdf.cell(4.0, 0.6, text=_("Start:"), border=borders, align='L')
            pdf.cell(5.0, 0.6, text=f"{self.event.start_time_in_timezone.strftime('%H:%M %d.%m.%Y %Z')}", border=borders, align='L')

            pdf.cell(2.5, 0.6, text=_("Duration:"), border=borders, align='R')
            pdf.cell(2.5, 0.6, text=f"{self.event.duration_minutes} min", border=borders, align='L')

            pdf.ln(0.75)  # Move to the next line
            pdf.cell(4.0, 0.6, text=_("Venue:"), border=borders, align='L')
            pdf.cell(10.0, 0.6, text=f"{self.event.location.get_address()}", border=borders,  align='L')
            
            pdf.ln(0.75)  # Move to the next line
            if self.event.display_seat_number:
                pdf.cell(4.0, 0.6, text=_("Seat Number:"), border=borders, align='L')
                pdf.cell(2.0, 0.6, text=f"{self.seat}", border=borders,  align='L')
            else:
                pdf.cell(4.0, 0.6, text=_("Free Seating"), border=borders, align='L')


            pdf.ln(1.25)  # Move to the next line
            pdf.cell(4.0, 0.6, text=_("Price Class:"), border=borders, align='L')
            pdf.cell(4.0, 0.6, text=f"{self.price_class.name}", border=borders, align='L') 
            if self.price_class.notification_message:
                pdf.ln(0.55)
                pdf.set_font(font, size=10)
                pdf.cell(4.0, 0.35, text="", border=borders, align='L')
                pdf.multi_cell(10.0, 0.35, text=f"{self.price_class.notification_message}", border=borders, align='L')
                pdf.set_font(font, size=15)
                pdf.ln(0.1) 
            else:
                pdf.ln(0.75)  # Move to the next line
            pdf.cell(4.0, 0.6, text=_("Price:"), border=borders, align='L')
            pdf.cell(4.0, 0.6, text=f"{self.price_class.price} {settings.DEFAULT_CURRENCY}", border=borders, align='L')

            # render ticket footer
            pdf.set_font(font, size=10)
            pdf.set_y(-0.75)  # Set position 2.5 cm from the bottom
            pdf.cell(7, 0.4, text=f"{self.id}", border=borders, align='L')
            pdf.ln(-0.5)
            pdf.cell(7.0, 0.4, text=f"{self.first_name} {self.last_name}", border=borders, align='L')
            pdf.cell(7.0, 0.4, text=f"{self.email}", border=borders, align='L')


            ## Ticket Check Side
            # vertical line to divide ticket into two parts
            pdf.line(14.75, 0.1, 14.75, 8.4)

            # Add QR Code to the Bottom Right
            pdf.image(qr_image_path, x=15.5, y=0.0, w=5, h=5)  # Adjust size and position of the QR code

            pdf.set_font(font, size=8)
            pdf.set_y(5.2)  # Set x position for ticket check side
            pdf.set_x(15.2)  # Set x position for ticket check side
            pdf.cell(5.5, 0.5, text=f"{self.event.name}", border=borders, align='C', new_y="NEXT", new_x="LEFT")
            pdf.cell(5.5, 0.5, text=f"{self.event.start_time_in_timezone.strftime('%H:%M %d.%m.%Y %Z')} {self.event.duration_minutes} min", border=borders, align='C', new_y="NEXT", new_x="LEFT")
            if self.event.display_seat_number:
                pdf.cell(5.5, 0.5, text=f"{self.seat}", border=borders, align='C', new_y="NEXT", new_x="LEFT")
            else:
                pdf.cell(5.5, 0.5, text=_("Free Seating"), border=borders, align='C', new_y="NEXT", new_x="LEFT")
            pdf.cell(5.5, 0.5, text=f"{self.event.location.get_address()}", border=borders, align='C', new_y="NEXT", new_x="LEFT")
            
        finally:
            # Clean up the temporary QR code image
            if os.path.exists(qr_image_path):
                os.remove(qr_image_path)

        return pdf

    def send_to_email(self):
        """
        Send the ticket to the email address associated with the ticket.
        """
        branding = get_active_branding()

        if self.email:
            if branding and branding.invoice_tax_rate:
                site_name = branding.site_name
            else:
                site_name = "Cinema Ticketing"

            subject = _("Your Ticket for {event_name} - {site_name}").format(event_name=self.event.name, site_name=site_name)

            if branding and branding.display_seat_number:
                seat = self.seat
            else:
                seat = _("Free Seating")

            message = _("Dear Customer,\n\nHere is your ticket for {event_name}.\n\n"
                        "Event: {event_name}\n"
                        "Date and Time: {start_time} Duration: {duration}\n"
                        "Seat: {seat}\n\n"
                        "Thank you for your purchase!\n\n"
                        "Best regards,\nEvent Team").format(
                            event_name=self.event.name,
                            start_time=self.event.start_time_in_timezone.strftime('%H:%M %d.%m.%Y %Z'),
                            duration=self.event.duration,
                            seat=seat
                        )
            
            # Generate PDF ticket
            pdf = self.generate_pdf_ticket()
            # Create a BytesIO stream to hold the PDF data
            pdf_output = pdf.output(dest='S')  # Get PDF as a bytearray

            email = EmailMessage(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.email]
            )
            email.attach(f"ticket_{self.id}.pdf", pdf_output, 'application/pdf')
            
            try:
                email.send()
            except Exception as e:
                # Log the error or handle it as needed
                logger.error(f"Error sending email: {e}")
                raise e
        else:
            raise ValueError(_("No email address associated with this ticket."))

    def queue_send_to_email(self):
        if settings.EMAILS_ASYNC:
            from .tasks import send_ticket_email_task

            transaction.on_commit(lambda: send_ticket_email_task.delay(str(self.pk)))
            return

        self.send_to_email()

class Event(models.Model):
    """
    Global event model.
    """
    name = models.CharField(
        _("name"), 
        max_length=255,
        help_text=_("Name of the event, e.g., 'Movie Night: Inception' or 'Live Concert: The Beatles Tribute'")
    )
    
    start_time = models.DateTimeField(
        _("start time"),
        help_text=_("Start time of the event in default branding timezone. The time will be displayed to users in the event's timezone, which can be customized for each event. If no custom timezone is set for the event, the default branding timezone will be used.")
    )

    custom_event_timezone = models.CharField(
        _("custom event timezone"),
        max_length=63,
        blank=True,
        null=True,
        choices=[(tz, tz) for tz in common_timezones],
        help_text=_("Custom timezone for this event. If not set, the default timezone will be used.")
    )
    
    duration = models.DurationField(
        _("duration"), 
        default='02:00:00',
        help_text=_("Duration of the event (e.g., 2 hours would be '02:00:00').")
    )

    location = models.ForeignKey(
        Location, 
        verbose_name=_("location"), 
        on_delete=models.CASCADE,
        help_text=_("Location where the event takes place. The location defines the total number of seats available for the event and can have a default color for the event card view.")
    )

    price_classes = models.ManyToManyField(
        PriceClass, 
        verbose_name=_("price classes"), 
        related_name="events",
        help_text=_("Price classes available for this event. You can define different price classes (e.g., VIP, Regular) with different prices and optional notification messages. Secret price classes will only be shown to staff and in door selling.")
    )
    
    program_link = models.URLField(
        _("program link"), 
        blank=True, 
        null=True,
        help_text=_("Optional link to the event program or more information about the event (e.g., a link to the movie details or concert information).")
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # event id

    is_active = models.BooleanField(
        _("is active"), 
        default=True,
        help_text=_("Whether the event is active. Inactive events will not be shown to users and cannot be booked. The status is automatically updated based on the event start time and duration, but can also be manually set here.")
    )
    
    custom_seats = models.PositiveIntegerField(
        _("custom seats"), 
        null=True, 
        blank=True,
        help_text=_("Custom total number of seats for this event. If not set, the total seats from the location will be used.")
    )

    custom_displayed_color = models.CharField(
        _("custom displayed color"),
        max_length=7,
        blank=True,
        null=True,
        choices=BOOTSTRAP_COLORS,
        help_text=_("Selected the color for the card view of the event. If not set, the default color from location will be used. If 'Custom Color' is selected, enter a hex color code in the 'Custom Color' field.")
    )
    custom_color = models.CharField(
        _("custom color"),
        max_length=7,
        blank=True,
        null=True,
        help_text=_("Hex color code if 'Custom Color' is selected (e.g., #007bff)")
    )
    
    custom_ticket_background = models.ImageField(
        _("ticket background"), 
        upload_to='event/images', 
        null=True, 
        blank=True, 
        help_text=_("Custom background image for the ticket. If not set, the default background from branding will be used.")
    )

    custom_display_seat_number = models.BooleanField(
        _("display seat number"),
        null=True,
        blank=True,
        help_text=_("Whether to display the seat number on the ticket. If not set, the default setting from branding will be used.")
    )
    
    custom_event_background = models.ImageField(
        _("event background"), 
        upload_to='event/images', 
        null=True, 
        blank=True, 
        help_text=_("Custom background image for the event card. If not set, the default background from branding will be used.")
    )
    
    custom_allow_presale = models.BooleanField(
        _("allow presale"), 
        null=True,
        blank=True,
        help_text=_("Whether to allow presale tickets. If not set, the default setting from branding will be used.")
    )

    custom_presale_start = models.DateTimeField(
        _("presale start"),
        null=True,
        blank=True,
        help_text=_("Start time for presale tickets. If not set, the default setting from branding will be used.")
    )

    custom_presale_ends_before = models.IntegerField(
        _("presale ends before and door (not presale) selling starts"), 
        null=True,
        blank=True,
        help_text=_("Number of hours before event start when presale ends and door selling starts. If not set, the default setting from branding will be used.")
    )
    
    custom_allow_door_selling = models.BooleanField(
        _("allow door selling"), 
        null=True,
        blank=True,
        help_text=_("Whether to allow door selling. If not set, the default setting from branding will be used.")
    )

    def __str__(self):
        return self.name

    def _convert_to_event_timezone(self, value):
        """Return a datetime converted to the resolved event timezone."""
        if value is None:
            return None
        if django.utils.timezone.is_naive(value):
            value = django.utils.timezone.make_aware(value, timezone.utc)

        print(f"Converting {value} to timezone {self.timezone}: {value.astimezone(self.timezone)}")
        return value.astimezone(self.timezone)

    @property
    def duration_minutes(self):
        """
        Return the duration of the event in minutes.
        """
        return self.duration.total_seconds() / 60

    @property
    def presale_end_time(self):
        """
        Returns time when presale ends. 
        """
        return self.start_time - timedelta(hours=self.presale_ends_before)
    
    def check_active(self):
        """
        Check if the event is active.
        """
        if self.start_time + self.duration < datetime.now(timezone.utc):
            self.is_active = False
            self.save()
        return self.is_active
    
    @property
    def color(self):
        """Return the color to use - either color from event or from location"""
        if self.custom_displayed_color == "custom":
            if self.custom_color:
                return self.custom_color
            # Fallback to default color if custom is selected but no custom_color is set
            return BOOTSTRAP_COLORS[0][0]  # Default blue color
        if self.custom_displayed_color:
            return self.custom_displayed_color
        return self.location.get_color()

    @property
    def color_rgb(self):
        """Convert hex color to RGB tuple as string (e.g., '13, 202, 240')"""
        color = self.color
        # Remove # if present
        color = color.lstrip('#')
        # Convert hex to RGB
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        return f"{r}, {g}, {b}"

    @property
    def timezone(self):
        """Return the pytz timezone object for this event."""
        if self.custom_event_timezone:
            return pytz_timezone(self.custom_event_timezone)
        # Fetch active branding dynamically to avoid stale cached values
        active_branding = get_active_branding()
        return pytz_timezone(active_branding.default_event_timezone) if active_branding and active_branding.default_event_timezone else pytz_timezone('UTC')

    @property
    def start_time_in_timezone(self):
        """Return the start time converted to the event's timezone."""
        return self._convert_to_event_timezone(self.start_time)

    @property
    def presale_start_time_in_timezone(self):
        """Return the presale start time converted to the event's timezone."""
        return self._convert_to_event_timezone(self.presale_start)

    @property
    def presale_end_time_in_timezone(self):
        """Return the presale end time converted to the event's timezone."""
        return self._convert_to_event_timezone(self.presale_end_time)

    @property
    def ticket_background(self):
        """
        Return the ticket background image for this event, or None if not set.
        """
        if self.custom_ticket_background and os.path.exists(self.custom_ticket_background.path):
            return self.custom_ticket_background.path
        active_branding = get_active_branding()
        if active_branding and active_branding.ticket_background and os.path.exists(active_branding.ticket_background.path):
            return active_branding.ticket_background.path
        return None

    @property
    def total_seats(self):
        """
        Return the total number of seats for this event, either from the event itself or from the location.
        """
        if self.custom_seats is not None:
            return self.custom_seats
        return self.location.total_seats

    @property
    def display_seat_number(self):
        """
        Return whether to display the seat number on the ticket, either from the event itself or from the branding.
        """
        if self.custom_display_seat_number is not None:
            return self.custom_display_seat_number
        active_branding = get_active_branding()
        if active_branding and active_branding.display_seat_number is not None:
            return active_branding.display_seat_number
        return True  # Default to displaying seat number

    @property
    def allow_presale(self):
        """
        Return whether to allow presale tickets, either from the event itself or from the branding.
        """
        if self.custom_allow_presale is not None:
            return self.custom_allow_presale
        active_branding = get_active_branding()
        if active_branding and active_branding.allow_presale is not None:
            return active_branding.allow_presale
        return True  # Default to allowing presale

    @property
    def presale_start(self):
        """
        Return the presale start time, either from the event itself or from the branding.
        """
        if self.custom_presale_start is not None:
            return self.custom_presale_start
        active_branding = get_active_branding()
        if active_branding and active_branding.presale_start is not None:
            return active_branding.presale_start
        return self.start_time - timedelta(days=7)  # Default to starting presale 7 days before event

    @property
    def presale_ends_before(self):
        """
        Return the number of hours before event start when presale ends and door selling starts, either from the event itself or from the branding.
        """
        if self.custom_presale_ends_before is not None:
            return self.custom_presale_ends_before
        active_branding = get_active_branding()
        if active_branding and active_branding.presale_ends_before is not None:
            return active_branding.presale_ends_before
        return 2  # Default to ending presale 2 hours before event

    @property
    def allow_door_selling(self):
        """
        Return whether to allow door selling, either from the event itself or from the branding.
        """
        if self.custom_allow_door_selling is not None:
            return self.custom_allow_door_selling
        active_branding = get_active_branding()
        if active_branding and active_branding.allow_door_selling is not None:
            return active_branding.allow_door_selling
        return True  # Default to allowing door selling

    @property
    def event_background(self):
        """
        Return the event background image for this event, or None if not set.
        """
        if self.custom_event_background and os.path.exists(self.custom_event_background.path):
            return self.custom_event_background.path
        active_branding = get_active_branding()
        if active_branding and active_branding.event_background and os.path.exists(active_branding.event_background.path):
            return active_branding.event_background.path
        return None

    def calculate_statistics(self):
        """
        Calculate statistics for the event.
        """
        tickets = Ticket.objects.filter(event=self)
        price_classes = self.price_classes.all()

        total_stats = {
            'waiting': tickets.filter(sold_as=SoldAsStatus.WAITING).count(),
            'presale_online_waiting': tickets.filter(sold_as=SoldAsStatus.PRESALE_ONLINE_WAITING).count(),
            'presale_online': tickets.filter(sold_as=SoldAsStatus.PRESALE_ONLINE).count(),
            'presale_door': tickets.filter(sold_as=SoldAsStatus.PRESALE_DOOR).count(),
            'door': tickets.filter(sold_as=SoldAsStatus.DOOR).count(),
            'total_sold': tickets.exclude(sold_as__in=[SoldAsStatus.WAITING, SoldAsStatus.PRESALE_ONLINE_WAITING]).count(),
            'total_count': tickets.all().count(),
            'activated_presale_online': tickets.filter(sold_as=SoldAsStatus.PRESALE_ONLINE, activated=True).count(),
            'activated_presale_door': tickets.filter(sold_as=SoldAsStatus.PRESALE_DOOR, activated=True).count(),
            'activated_door': tickets.filter(sold_as=SoldAsStatus.DOOR, activated=True).count(),
            'total_activated': tickets.filter(activated=True).count(),
            'earned_presale_online': 0,
            'earned_presale_door': 0,
            'earned_door': 0,
            'total_earned': 0
        }
        price_class_stats = {}

        for price_class in price_classes:
            waiting_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.WAITING).count()
            presale_online_waiting_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.PRESALE_ONLINE_WAITING).count()
            presale_online_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.PRESALE_ONLINE).count()
            presale_door_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.PRESALE_DOOR).count()
            door_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.DOOR).count()
            
            activated_waiting_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.WAITING, activated=True).count()
            activated_presale_online_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.PRESALE_ONLINE, activated=True).count()
            activated_presale_door_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.PRESALE_DOOR, activated=True).count()
            activated_door_count = tickets.filter(price_class=price_class, sold_as=SoldAsStatus.DOOR, activated=True).count()
            
            earned_presale_online = presale_online_count * price_class.price
            earned_presale_door = presale_door_count * price_class.price
            earned_door = door_count * price_class.price
            
            total_stats['earned_presale_online'] += earned_presale_online
            total_stats['earned_presale_door'] += earned_presale_door
            total_stats['earned_door'] += earned_door
            
            earned = (presale_online_count + presale_door_count + door_count) * price_class.price
            total_stats['total_earned'] += earned


            price_class_stats[price_class] = {
                'waiting': waiting_count,
                'presale_online_waiting': presale_online_waiting_count,
                'presale_online': presale_online_count,
                'presale_door': presale_door_count,
                'door': door_count,
                'total_sold': presale_online_count + presale_door_count + door_count,
                'total_count': waiting_count + presale_online_waiting_count + presale_online_count + presale_door_count + door_count,
                'activated_presale_online': activated_presale_online_count,
                'activated_presale_door': activated_presale_door_count,
                'activated_door': activated_door_count,
                'total_activated': activated_waiting_count + activated_presale_online_count + activated_presale_door_count + activated_door_count,
                'earned_presale_online': earned_presale_online,
                'earned_presale_door': earned_presale_door,
                'earned_door': earned_door,
                'total_earned': earned,
            }

        return total_stats, price_class_stats
    
    def generate_statistics_pdf(self):
        """
        Generate a PDF with statistics for the event.
        """
        # Create the PDF
        pdf = FPDF(unit="cm", format=(21.0, 29.7))  # A4 format
        pdf.set_margins(1.0, 1.0)
        pdf.set_auto_page_break(auto=True, margin=0.2)
        pdf.add_page()
        font = "Helvetica"
        pdf.set_font(font, size=18, style='B')
        pdf.cell(19.0, 1.0, text=f"{self.name} - Statistics", border=0, align='C')
        pdf.ln(1.0)
        pdf.set_font(font, size=12, style='B')
        pdf.cell(4.0, 0.6, text=_("Start:"), border=0, align='L')
        pdf.cell(5.0, 0.6, text=f"{self.start_time_in_timezone.strftime('%H:%M %d.%m.%Y %Z')}", border=0, align='L')
        pdf.ln(0.8)
        pdf.cell(4.0, 0.6, text=_("Venue:"), border=0, align='L')
        pdf.cell(10.0, 0.6, text=f"{self.location.name}", border=0, align='L')
        pdf.ln(0.8)

        # created at
        pdf.set_font(font, size=10)
        pdf.cell(19.0, 0.6, text=f"Created at: {datetime.now().strftime('%d.%m.%Y %H:%M')}", border=0, align='L')
        pdf.ln(0.6)

        # Fetch statistics
        total_stats, price_class_stats = self.calculate_statistics()

        # Add total statistics
        pdf.set_font(font, size=12, style='B')
        pdf.cell(19.0, 0.8, text="Total Statistics", border=0, align='L')
        pdf.ln(0.8)
        pdf.set_font(font, size=10)

        # Create table for total statistics
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(9.0, 0.6, text="Statistic", border=1, align='C', fill=True)
        pdf.cell(10.0, 0.6, text="Value", border=1, align='C', fill=True)
        pdf.ln(0.6)
        for key, value in total_stats.items():
            display_value = f"{value} {settings.DEFAULT_CURRENCY}" if 'earned' in key else value
            pdf.cell(9.0, 0.6, text=f"{key.replace('_', ' ').title()}", border=1, align='L')
            pdf.cell(10.0, 0.6, text=f"{display_value}", border=1, align='L')
            pdf.ln(0.6)

        pdf.ln(1.0)

        # Add price class statistics
        pdf.set_font(font, size=12, style='B')
        pdf.cell(19.0, 0.8, text="Price Class Statistics", border=0, align='L')
        pdf.ln(0.8)
        pdf.set_font(font, size=10)


        # Create table for price class statistics
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(5.0, 1.2, text="Statistic", border=1, align='C', fill=True)
        for price_class in price_class_stats.keys():
            pdf.multi_cell(3.0, 1.2, text=f"{price_class.name}", border=1, align='C', fill=True, ln=3, max_line_height=pdf.font_size*1.5)
        pdf.ln(1.2)
        pdf.cell(5.0, 0.6, text=f"Price", border=1, align='C', fill=True)
        for price_class in price_class_stats.keys():
            pdf.cell(3.0, 0.6, text=f"{price_class.price} {settings.DEFAULT_CURRENCY}", border=1, align='C', fill=True)
        pdf.ln(0.6)
        for key in next(iter(price_class_stats.values())).keys():
            pdf.cell(5.0, 0.6, text=f"{key.replace('_', ' ').title()}", border=1, align='L')
            for price_class, stats in price_class_stats.items():
                display_value = f"{stats[key]} {settings.DEFAULT_CURRENCY}" if 'earned' in key else stats[key]
                pdf.cell(3.0, 0.6, text=f"{display_value}", border=1, align='L')
            pdf.ln(0.6)

        return pdf

    @property
    def remaining_seats(self):
        """
        Return the number of seats still available for this event.
        If custom_seats is set, use that; otherwise, fallback to the location's total_seats.
        """
        total_seats = self.total_seats
        sold_tickets = Ticket.objects.filter(event=self).all().count()  # Count sold tickets for the event
        return total_seats - sold_tickets  # Subtract sold tickets from total seats
    
    @property
    def is_sold_out(self):
        """
        Check if the event is sold out.
        """
        return self.remaining_seats <= 0

class TicketMaster(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ticket_master_profile',
        help_text=_("Optional direct link to the Django user for this ticket manager."),
    )
    firstname = models.CharField(max_length=100, help_text=_("Enter the first name"))
    lastname = models.CharField(max_length=100, help_text=_("Enter the last name"))
    email = models.EmailField(help_text=_("Enter the email address to which all ticket sales are sent"))
    is_active = models.BooleanField(default=False, help_text=_("Indicates if the contact is active"))

    active_locations = models.ManyToManyField(Location, blank=True, help_text=_("Select the locations for which this ticket master is responsible. If no location is selected this ticket master will be responsible for all locations."))

    def __str__(self):
        return f"{self.firstname} {self.lastname}"    

    @classmethod
    def for_user(cls, user):
        if not user or not user.is_authenticated:
            return None

        ticket_master = cls.objects.filter(user=user).first()
        if ticket_master:
            return ticket_master

        if user.email:
            return cls.objects.filter(email=user.email, is_active=True).first()
        return None
    
    def get_active_locations(self):
        """
        Return the active locations for this ticket master. If no location is selected, return all locations.
        """
        if self.active_locations.exists():
            return self.active_locations.all()
        else:
            return Location.objects.all()
    
    # when saved add to Ticket Managers group and when deactivated remove from group
    def save(self, *args, **kwargs):
        from django.contrib.auth.models import Group
        from django.contrib.auth import get_user_model

        User = get_user_model()

        with transaction.atomic():
            # Get or create the 'Ticket Managers' group before saving the instance
            ticket_managers_group, created = Group.objects.get_or_create(name='Ticket Managers')

            # Update user groups and staff status before saving the ticket master
            user = None
            if self.user:
                # Prefer direct FK link to user
                user = self.user
            elif self.email:
                # Fall back to email lookup only if no direct user link
                try:
                    user = User.objects.get(email=self.email)
                except User.DoesNotExist:
                    logger.debug(f"No user found with email {self.email} for ticket master {self.firstname} {self.lastname}")
                except User.MultipleObjectsReturned:
                    logger.warning(f"Multiple users found with email {self.email} for ticket master {self.firstname} {self.lastname}. Using user FK only.")

            # Update user's group and is_staff status
            if user:
                if self.is_active:
                    if not user.is_staff:
                        user.is_staff = True
                        user.save(update_fields=['is_staff'])
                    user.groups.add(ticket_managers_group)  # Add to group if active
                else:
                    user.groups.remove(ticket_managers_group)  # Remove from group if not active
                    if (
                        user.is_staff
                        and not user.is_superuser
                        and not user.groups.filter(name__in=['admin', 'Admins']).exists()
                    ):
                        user.is_staff = False
                        user.save(update_fields=['is_staff'])

            # Save the ticket master instance only after user operations succeed
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.contrib.auth.models import Group
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Get the 'Ticket Managers' group
        ticket_managers_group = Group.objects.filter(name='Ticket Managers').first()

        # Find the user associated with this ticket master
        try:
            user = self.user or User.objects.get(email=self.email)
            if ticket_managers_group:
                user.groups.remove(ticket_managers_group)  # Remove from group when ticket master is deleted
            if (
                user.is_staff
                and not user.is_superuser
                and not user.groups.filter(name__in=['admin', 'Admins']).exists()
            ):
                user.is_staff = False
                user.save(update_fields=['is_staff'])
        except User.DoesNotExist:
            pass  # If no user exists with this email, do nothing

        super().delete(*args, **kwargs)  # Call the original delete method to delete the instance
        