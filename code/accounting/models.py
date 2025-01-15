from django.db import models
from django.utils import timezone
from datetime import timedelta, datetime
from typing import Iterable
from decimal import Decimal

from events.models import Ticket
from branding.models import get_active_branding

from payments.models import BasePayment, PaymentStatus, PurchasedItem
from django.core.mail import EmailMessage
from django.contrib import messages
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.shortcuts import redirect
from django.urls import reverse

from fpdf import FPDF
import os
# class for holding one sessions order until payment is completed
class Order(BasePayment):
    """
    Custom payment model that extends django-payments' BasePayment model
    """
    
    session_id = models.CharField(max_length=255, unique=True)
    tickets = models.ManyToManyField(Ticket, related_name="Tickets")

    timeout = models.IntegerField(default=10)  # in minutes

    variant = "stripe" 

    currency = models.CharField(max_length=10, default=settings.DEFAULT_CURRENCY)

    def get_purchased_items(self) -> Iterable[PurchasedItem]:
        """Return an iterable of purchased items.

        This information is sent to the payment processor when initiating the payment
        flow. See :class:`.PurchasedItem` for details.
        """
        for ticket in self.tickets.all():
            branding = get_active_branding()
            if branding and branding.invoice_tax_rate:
                tax_rate = branding.invoice_tax_rate
            else:
                tax_rate = 0.0
            yield PurchasedItem(
                name=ticket.event.name,
                quantity=1,
                price=ticket.price_class.price,
                currency=ticket.price_class.price.currency,
                sku=ticket.id,
                tax_rate=tax_rate,
            )

    def get_failure_url(self) -> str:
        """URL where users will be redirected after a failed payment.

        Return the URL where users will be redirected after a failed attempt to complete
        a payment. This is usually a page explaining the situation to the user with an
        option to retry the payment.

        Note that the URL may contain the ID of this payment, allowing
        the target page to show relevant contextual information.
        """
        return "http://127.0.0.1:8000" + reverse('cart_view')

    def get_success_url(self) -> str:
        """URL where users will be redirected after a successful payment.

        Return the URL where users will be redirected after a successful payment. This
        is usually a page showing a payment summary, though it's application-dependant
        what to show on it.

        Note that the URL may contain the ID of this payment, allowing
        the target page to show relevant contextual information.
        """
        return "http://127.0.0.1:8000" + reverse('ticket_list' , kwargs={'order_id': self.session_id})


    #def __str__(self):
    #    return f"Payment {self.id}"

    # set to branding order_timeout if available
    if get_active_branding() and get_active_branding().order_timeout:
        timeout = get_active_branding().order_timeout

    def __str__(self):
        return _("Order {id} for session {session_id}").format(id=self.id, session_id=self.session_id)

    def is_valid(self) -> bool:
        if self.status == PaymentStatus.CONFIRMED:
            return True
        if self.modified is None:
            return False
        return timezone.now() - self.modified <= timedelta(minutes=self.timeout)

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
        self.modified = timezone.now()
        self.save()
    
    def delete_ticket(self, ticket):
        # remove ticket from order
        self.tickets.remove(ticket)
        # delete ticket
        ticket.delete()
        # calculate new total amount
        self.total = sum(ticket.price_class.price for ticket in self.tickets.all())  # Sum ticket prices
        self.modified = timezone.now()
        self.save()
    
    def reset_timeout(self):
        self.modified = timezone.now()
        self.save()

    def get_remaining_time(self):
        return self.timeout - (timezone.now() - self.modified).seconds // 60
    
    def generate_pdf_invoice(self):
        """
        Generate a PDF invoice for the order.
        """
        branding = get_active_branding()
        # if branding has these, otherwise blank
        if branding:
            company_name = branding.invoice_company_name
            company_address_1 = branding.invoice_address_1
            company_address_2 = branding.invoice_address_2
            company_address_city = branding.invoice_city
            company_address_postcode = branding.invoice_postal_code
            company_address_country = branding.invoice_country
            company_vat = branding.invoice_vat_id
            company_phone = branding.invoice_phone
            company_email = branding.invoice_email
        else:
            company_name = _("Company Name")
            company_address_1 = _("Company Address")
            company_address_2 = ""
            company_address_city = _("City")
            company_address_postcode = _("Postcode")
            company_address_country = _("Country")
            company_vat = _("VAT Number")
            company_phone = _("Phone Number")
            company_email = _("Email Address")

        invoice_number = _("INV-{invoice_id}").format(invoice_id=self.id)
        date = datetime.today().strftime('%Y-%m-%d')
        due_date = (self.created + timedelta(days=30)).strftime('%Y-%m-%d')
        bill_to = (
            f"{self.payment.billing_first_name} {self.payment.billing_last_name}\n"
            f"{self.payment.billing_address_1}\n"
            f"{self.payment.billing_address_2}\n"
            f"{self.payment.billing_city}\n"
            f"{self.payment.billing_postcode}\n"
            f"{self.payment.billing_country_code}\n"
            f"{self.payment.billing_country_area}"
        )
        if branding and branding.invoice_tax_rate:
            tax_rate = branding.invoice_tax_rate
        else:
            tax_rate = 0.0

        # Calculate totals
        items = [{"description": ticket.event.name, "qty": 1, "unit_price": ticket.price_class.price.amount} for ticket in self.tickets.all()]
        subtotal_with_tax = sum(item["qty"] * item["unit_price"] for item in items)
        tax = subtotal_with_tax * tax_rate
        subtotal = subtotal_with_tax - tax
        total = subtotal + tax

        # Create the PDF
        pdf = FPDF(unit="cm", format="A4")
        pdf.set_margins(1, 1)
        pdf.set_auto_page_break(auto=True, margin=1)

        # If a template is provided, use it as the canvas
        if branding and branding.invoice_background:
            if os.path.exists(branding.invoice_background.path):
                try:
                    pdf.set_page_background(branding.invoice_background.path)
                except Exception as e:
                    print(f"Error loading template image: {e}")
            else:
                pdf.set_page_background(None)  # Proceed without a template if not found
                print("Template file not found. Proceeding without it.")

        pdf.add_page()
        font = "Helvetica"
        pdf.set_font(font)

        # Add company details
        pdf.set_font(font, size=12)
        pdf.multi_cell(0, 0.6, f"{company_name}\n{company_address_1}\n{company_address_2}\n{company_address_city}\n{company_address_postcode}\n{company_address_country}\n\n{_('Invoice #:')} {invoice_number}\n{_('Date:')} {date}\n{_('Due Date:')} {due_date}")


        # Add "Bill To" section
        pdf.ln(1)
        pdf.set_font(font, size=14, style='B')
        pdf.cell(0, 0.6, _("Invoice To:"), ln=1)
        pdf.set_font(font, size=12)
        pdf.multi_cell(0, 0.6, bill_to)

        # Add table header
        pdf.ln(1)
        pdf.set_font(font, size=12, style='B')
        pdf.cell(8, 0.6, _("Description"), border=1)
        pdf.cell(3, 0.6, _("Quantity"), border=1, align="C")
        pdf.cell(4, 0.6, _("Unit Price"), border=1, align="C")
        pdf.cell(4, 0.6, _("Total"), border=1, align="C")
        pdf.ln()

        # Add table rows
        pdf.set_font(font, size=12)
        for item in items:
            pdf.cell(8, 0.6, item["description"], border=1)
            pdf.cell(3, 0.6, str(item["qty"]), border=1, align="C")
            pdf.cell(4, 0.6, f"${item['unit_price']:.2f}", border=1, align="C")
            pdf.cell(4, 0.6, f"${item['qty'] * item['unit_price']:.2f}", border=1, align="C")
            pdf.ln()

        # Add totals
        pdf.set_font(font, size=12, style='B')
        pdf.cell(15, 0.6, _("Subtotal"), border=1)
        pdf.cell(4, 0.6, f"${subtotal:.2f}", border=1, align="C")
        pdf.ln()

        pdf.cell(15, 0.6, _("Tax ({tax_rate}%)").format(tax_rate=tax_rate * 100), border=1)
        pdf.cell(4, 0.6, f"${tax:.2f}", border=1, align="C")
        pdf.ln()

        pdf.cell(15, 0.6, _("Total"), border=1)
        pdf.cell(4, 0.6, f"${total:.2f}", border=1, align="C")
        pdf.ln()

        return pdf

    def send_confirmation_email(self):
        """
        Send a confirmation email to the user after the order is confirmed.
        """
        if self.status == PaymentStatus.CONFIRMED:
            subject = _("Your Invoice for {site_name}").format(site_name=get_active_branding().site_name)
            message = _("Dear Customer,\n\nThank you for your purchase! "
                        "You can find the invoice of your ticket purchase attached.\n\n"
                        "Please find your tickets and purchase details under the following link:\n\n"
                        "{order_link}\n\n"
                        "We look forward to seeing you at the event.\n\n"
                        "Best regards,\nThe Event Team").format(
                            order_link=redirect('ticket_list', order_id=self.session_id)
                        )
            
            # Generate PDF ticket
            pdf = self.generate_pdf_invoice()
            # Create a BytesIO stream to hold the PDF data
            pdf_output = pdf.output(dest='S')  # Get PDF as a bytearray

            email = EmailMessage(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.payment.billing_email]
            )
            email.attach(f"order_invoice_{self.session_id}.pdf", pdf_output, 'application/pdf')
            email.send()

    # delete order and associated tickets
    def delete(self, *args, **kwargs):
        if self.status == PaymentStatus.CONFIRMED:
            if settings.CONFIRM_DELETE_PAID_ORDER:
                messages.warning(None, _("Cannot delete a paid order."))
                return None
            else:
                messages.warning(None, _("You are about to delete a paid order. All associated tickets will also be deleted."))
        
        self.tickets.all().delete() 
        super().delete(*args, **kwargs)


