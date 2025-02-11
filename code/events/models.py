from django.db import models
from django.conf import settings

from django.core.mail import EmailMessage
from django.utils.translation import gettext_lazy as _
import django.utils.timezone

from datetime import datetime, timedelta, timezone

from fpdf import FPDF
import qrcode
import os
import tempfile
import uuid

from branding.models import get_active_branding

class SoldAsStatus:
    WAITING = "waiting"
    PRESALE_ONLINE = "presale_online"
    PRESALE_DOOR = "presale_door"
    DOOR = "door"
    REFUNDED = "refunded"
    
    CHOICES = [
        (WAITING, _("Ticket not yet sold")),
        (PRESALE_ONLINE, _("Ticket was sold in online presale")),
        (PRESALE_DOOR, _("Ticket was sold in door presale")),
        (DOOR, _("Ticket was sold at the door")),
        (REFUNDED, _("Ticket refunded")),
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

    def __str__(self):
        return self.name
    
    def get_address(self):
        return f"{self.street} {self.house_number}, {self.zip_code} {self.city}"

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
    sold_as = models.CharField(_("sold as"), max_length=14, choices=SoldAsStatus.CHOICES, default=SoldAsStatus.WAITING)  # How the ticket was sold

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
                if os.path.exists(self.event.ticket_background.path):
                    try:
                        pdf.set_page_background(self.event.ticket_background.path)
                    except Exception as e:
                        print(f"Error loading template image: {e}")
                else:
                    pdf.set_page_background(None)  # Proceed without a template if not found
                    #print("Template file not found. Proceeding without it.")
            
            pdf.add_page()
            borders = 0
            
            # Add Event Title
            pdf.set_font(font, size=18, style='B')
            pdf.cell(14, 0.65, text=f"{self.event.name}", border=borders, align='L')
            
            # Add Ticket Details in a Layout
            pdf.set_font(font, size=15)
            pdf.ln(1.25)  # Move to the next line

            pdf.cell(4.0, 0.6, text=_("Start:"), border=borders, align='L')
            pdf.cell(5.0, 0.6, text=f"{self.event.start_time.strftime('%H:%M %d.%m.%Y')}", border=borders, align='L')

            pdf.cell(2.5, 0.6, text=_("Duration:"), border=borders, align='R')
            pdf.cell(2.5, 0.6, text=f"{self.event.get_duration_minutes()} min", border=borders, align='L')

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
            pdf.cell(5.5, 0.5, text=f"{self.event.start_time.strftime('%H:%M %d.%m.%Y')} {self.event.get_duration_minutes()} min", border=borders, align='C', new_y="NEXT", new_x="LEFT")
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
        if self.email:
            subject = _("Your Ticket for {event_name}").format(event_name=self.event.name)
            message = _("Dear Customer,\n\nHere is your ticket for {event_name}.\n\n"
                        "Event: {event_name}\n"
                        "Date and Time: {start_time} Duration: {duration}\n"
                        "Seat: {seat}\n\n"
                        "Thank you for your purchase!\n\n"
                        "Best regards,\nEvent Team").format(
                            event_name=self.event.name,
                            start_time=self.event.start_time,
                            duration=self.event.duration,
                            seat=self.seat
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
            email.send()
        else:
            raise ValueError(_("No email address associated with this ticket."))

class Event(models.Model):
    """
    Global event model.
    """
    name = models.CharField(_("name"), max_length=255) # name of event
    start_time = models.DateTimeField(_("start time")) # start time of event
    duration = models.DurationField(_("duration"), default='02:00:00')  # 2 hours
    location = models.ForeignKey(Location, verbose_name=_("location"), on_delete=models.CASCADE) # add location to event
    price_classes = models.ManyToManyField(PriceClass, verbose_name=_("price classes"), related_name="events")  # multiple PriceClasses for an event
    program_link = models.URLField(_("program link"), blank=True, null=True) # link to website with program

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) # event id

    is_active = models.BooleanField(_("is active"), default=True) # event is active
    
    # Optional field to customize the number of seats for this event
    custom_seats = models.PositiveIntegerField(_("custom seats"), null=True, blank=True)  # If None, use total_seats from location


    branding = get_active_branding()
    
    ticket_background = models.ImageField(
        _("ticket background"), 
        upload_to='event/images', 
        null=True, 
        blank=True, 
        default=branding.ticket_background if branding and branding.ticket_background else None
    )

    display_seat_number = models.BooleanField(
        _("display seat number"),
        default=branding.display_seat_number if branding and branding.display_seat_number else False
    )
    
    event_background = models.ImageField(
        _("event background"), 
        upload_to='event/images', 
        null=True, 
        blank=True, 
        default=branding.event_background if branding and branding.event_background else None
    )
    
    allow_presale = models.BooleanField(
        _("allow presale"), 
        default=branding.allow_presale if branding and branding.allow_presale else True
    )

    presale_start = models.DateTimeField(
        _("presale start"),
        default=branding.presale_start if branding and branding.presale_start else django.utils.timezone.now
    )

    presale_ends_before = models.IntegerField(
        _("presale ends before and door (not presale) selling starts"), 
        default=branding.presale_ends_before if branding and branding.presale_ends_before else 1
    )
    
    allow_door_selling = models.BooleanField(
        _("allow door selling"), 
        default=branding.allow_door_selling if branding and branding.allow_door_selling else True
    )


    def __str__(self):
        return self.name
    
    def get_duration_minutes(self):
        """
        Return the duration of the event in minutes.
        """
        return self.duration.total_seconds() / 60
    
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

    def calculate_statistics(self):
        """
        Calculate statistics for the event.
        """
        tickets = Ticket.objects.filter(event=self)
        price_classes = self.price_classes.all()

        total_stats = {
            'waiting': tickets.filter(sold_as=SoldAsStatus.WAITING).count(),
            'presale_online': tickets.filter(sold_as=SoldAsStatus.PRESALE_ONLINE).count(),
            'presale_door': tickets.filter(sold_as=SoldAsStatus.PRESALE_DOOR).count(),
            'door': tickets.filter(sold_as=SoldAsStatus.DOOR).count(),
            'total_sold': tickets.exclude(sold_as=SoldAsStatus.WAITING).count(),
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
                'presale_online': presale_online_count,
                'presale_door': presale_door_count,
                'door': door_count,
                'total_sold': presale_online_count + presale_door_count + door_count,
                'total_count': waiting_count + presale_online_count + presale_door_count + door_count,
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
        pdf.cell(5.0, 0.6, text="Statistic", border=1, align='C', fill=True)
        for price_class in price_class_stats.keys():
            pdf.cell(4.0, 0.6, text=f"{price_class.name} - {price_class.price} {settings.DEFAULT_CURRENCY}", border=1, align='C', fill=True)
        pdf.ln(0.6)
        for key in next(iter(price_class_stats.values())).keys():
            pdf.cell(5.0, 0.6, text=f"{key.replace('_', ' ').title()}", border=1, align='L')
            for price_class, stats in price_class_stats.items():
                display_value = f"{stats[key]} {settings.DEFAULT_CURRENCY}" if 'earned' in key else stats[key]
                pdf.cell(4.0, 0.6, text=f"{display_value}", border=1, align='L')
            pdf.ln(0.6)

        return pdf

    @property
    def remaining_seats(self):
        """
        Return the number of seats still available for this event.
        If custom_seats is set, use that; otherwise, fallback to the location's total_seats.
        """
        total_seats = self.custom_seats if self.custom_seats is not None else self.location.total_seats
        sold_tickets = Ticket.objects.filter(event=self).all().count()  # Count sold tickets for the event
        return total_seats - sold_tickets  # Subtract sold tickets from total seats
    
    @property
    def is_sold_out(self):
        """
        Check if the event is sold out.
        """
        return self.remaining_seats <= 0

    @property
    def total_seats(self):
        """
        Return the total number of seats available for the event (either from the location or customized).
        """
        return self.custom_seats if self.custom_seats is not None else self.location.total_seats
