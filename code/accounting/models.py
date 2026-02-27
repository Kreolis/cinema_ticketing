from django.db import models
from django.utils import timezone
from datetime import timedelta, datetime
from typing import Iterable

from events.models import Ticket
from branding.models import get_active_branding, TicketMaster

from payments.models import BasePayment, PaymentStatus, PurchasedItem
from django.core.mail import EmailMessage
from django.contrib import messages
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from decimal import Decimal
from fpdf import FPDF
import os

import logging

logger = logging.getLogger(__name__)

# class for holding one sessions order until payment is completed
class Order(BasePayment):
    """
    Custom payment model that extends django-payments' BasePayment model
    """
    
    session_id = models.CharField(max_length=255, unique=True)
    tickets = models.ManyToManyField(Ticket, related_name="Tickets")

    timeout = models.IntegerField(default=10)  # in minutes

    # user choices for payment, limit choices to settings.PAYMENT_VARIANTS
    variant = models.CharField(max_length=255, choices=[(key, key) for key in settings.PAYMENT_VARIANTS.keys()], default=settings.DEFAULT_PAYMENT_VARIANT)

    currency = models.CharField(max_length=10, default=settings.DEFAULT_CURRENCY)

    failure_url = models.URLField(max_length=255, blank=True, null=True)
    success_url = models.URLField(max_length=255, blank=True, null=True)

    is_confirmed = models.BooleanField(default=False)

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
                currency=settings.DEFAULT_CURRENCY,
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

        return self.failure_url

    def get_success_url(self) -> str:
        """URL where users will be redirected after a successful payment.

        Return the URL where users will be redirected after a successful payment. This
        is usually a page showing a payment summary, though it's application-dependant
        what to show on it.

        Note that the URL may contain the ID of this payment, allowing
        the target page to show relevant contextual information.
        """
        return self.success_url

    # set to branding order_timeout if available
    if get_active_branding() and get_active_branding().order_timeout:
        timeout = get_active_branding().order_timeout

    def __str__(self):
        return _("Order {id} for session {session_id}").format(id=self.id, session_id=self.session_id)

    @property
    def has_timed_out(self) -> bool:
        return (timezone.now() - self.modified) > timedelta(minutes=self.timeout)

    def is_valid(self) -> bool:
        if self.status == PaymentStatus.CONFIRMED:
            return True
        if self.created is None or self.modified is None:
            return False
        return not self.has_timed_out

    def save(self, *args, **kwargs):
        if not self.pk and Order.objects.filter(session_id=self.session_id).exists():
            # order for this session already exists
            # return existing order instead of creating a new one
            existing_order = Order.objects.get(session_id=self.session_id)
            return existing_order

        if not self.created:
            self.created = timezone.now()
            self.modified = timezone.now()
        
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
    
    def get_payment_instructions(self, html=True):
        branding = get_active_branding()
        if branding:     
            due_days = branding.advanced_payment_due_days
            message = branding.advanced_payment_message
            iban = branding.advanced_payment_iban
            swift = branding.advanced_payment_swift
            bank_name = branding.advanced_payment_bank_name
            account_name = branding.advanced_payment_bank_account_name
            reference = branding.advanced_payment_reference
        else:
            due_days = 14
            message = _("Please transfer the total amount to the following bank account.")
            iban = "CH93 0076 2011 6238 5295 7"
            swift = "LFSACHZZXXX"
            bank_name = "Bank Name"
            account_name = "Account Name"
            reference = "cinema-ticketing-order"
        if html:
            payment_instructions = _(
                "<p>{message}</p>"
                "<p>Bank: <strong>{bank_name}</strong><br>"
                "Account Name: <strong>{account_name}</strong><br>"
                "IBAN: <strong>{iban}</strong><br>"
                "SWIFT: <strong>{swift}</strong></p>"
                "<p>Please use the following reference for your payment: <strong>{reference}</strong><br>"
                "Payment is due within <strong>{due_days}</strong> days.</p>"
                "<p>Thank you for your purchase!</p>").format(
                    message=message,
                    bank_name=bank_name,
                    account_name=account_name,
                    iban=iban,
                    swift=swift,
                    reference=f"{reference}-{self.id}",
                    due_days=due_days
            )
        else:
            payment_instructions = _(
                "{message}\n"
                "Bank: {bank_name}\n"
                "Account Name: {account_name}\n"
                "IBAN: {iban}\n"
                "SWIFT: {swift}\n"
                "Please use the following reference for your payment: {reference}\n"
                "Payment is due within {due_days} days.\n"
                "Thank you for your purchase!").format(
                    message=message,
                    bank_name=bank_name,
                    account_name=account_name,
                    iban=iban,
                    swift=swift,
                    reference=f"{reference}-{self.id}",
                    due_days=due_days
            )

        return payment_instructions
    
    def generate_pdf_invoice(self):
        """
        Generate a PDF invoice for the order.
        """
        branding = get_active_branding()
        # if branding has these, otherwise blank
        if branding:
            display_invoice_info = branding.display_invoice_info
            company_name = branding.invoice_company_name
            company_address_1 = branding.invoice_address_1
            company_address_2 = branding.invoice_address_2
            company_address_city = branding.invoice_city
            company_address_postcode = branding.invoice_postal_code
            company_address_country = branding.invoice_country
            company_vat = branding.invoice_vat_id
            company_phone = branding.invoice_phone
            company_email = branding.invoice_email
            invoice_padding_top = branding.invoice_padding_top
            invoice_padding_left = branding.invoice_padding_left
            invoice_padding_right = branding.invoice_padding_right
            invoice_padding_bottom = branding.invoice_padding_bottom
            reference = branding.advanced_payment_reference
        else:
            display_invoice_info = True
            company_name = _("Company Name")
            company_address_1 = _("Company Address")
            company_address_2 = ""
            company_address_city = _("City")
            company_address_postcode = _("Postcode")
            company_address_country = _("Country")
            company_vat = _("VAT Number")
            company_phone = _("Phone Number")
            company_email = _("Email Address")
            invoice_padding_top = 1
            invoice_padding_left = 1
            invoice_padding_right = 1
            invoice_padding_bottom = 1
            reference = _("INV")

        invoice_number = f"{reference}-{self.id}"  # Use the order ID as the invoice number
        date = datetime.today().strftime('%Y-%m-%d')
        due_date = (self.created + timedelta(days=30)).strftime('%Y-%m-%d')
        bill_to = (
            f"{self.billing_first_name} {self.billing_last_name}\n"
            f"{self.billing_address_1}\n"
            f"{self.billing_address_2}\n"
            f"{self.billing_city}\n"
            f"{self.billing_postcode}\n"
            f"{self.billing_country_code}\n"
            f"{self.billing_country_area}"
        )
        if branding and branding.invoice_tax_rate:
            tax_rate = branding.invoice_tax_rate/Decimal(100.0)
        else:
            tax_rate = Decimal(0.0)

        # Calculate totals
        items = [{"description": ticket.event.name, "qty": 1, "unit_price": ticket.price_class.price, "datetime": ticket.event.start_time} for ticket in self.tickets.all()]
        subtotal_with_tax = sum(item["qty"] * item["unit_price"] for item in items)
        tax = subtotal_with_tax * tax_rate
        subtotal = subtotal_with_tax - tax
        total = subtotal + tax

        # Create the PDF
        pdf = FPDF(unit="cm", format="A4")
        pdf.set_margins(left=invoice_padding_left, top=invoice_padding_top, right=invoice_padding_right)
        pdf.set_auto_page_break(auto=True, margin=invoice_padding_bottom)

        # If a template is provided, use it as the canvas
        if branding and branding.invoice_background:
            if os.path.exists(branding.invoice_background.path):
                try:
                    pdf.set_page_background(branding.invoice_background.path)
                except Exception as e:
                    logger.error(f"Error loading template image: {e}")
            else:
                pdf.set_page_background(None)  # Proceed without a template if not found
                logger.warning("Template file not found. Proceeding without it.")

        pdf.add_page()
        font = "Helvetica"
        pdf.set_font(font)

        if display_invoice_info:
            # Add company logo
            if branding and branding.invoice_logo:
                if os.path.exists(branding.invoice_logo.path):
                    pdf.image(branding.invoice_logo.path, x=invoice_padding_left, y=invoice_padding_top, w=3)
                else:
                    logger.warning("Logo file not found. Proceeding without it.")
            pdf.ln(3)
            # Add company details
            pdf.set_font(font, size=10)
            pdf.multi_cell(0, 0.5, f"{company_name}\n{company_address_1}\n{company_address_2}\n{company_address_city}\n{company_address_postcode}\n{company_address_country}\n\n{_('Invoice #:')} {invoice_number}\n{_('Date:')} {date}\n{_('Due Date:')} {due_date}")

        # Add "Bill To" section
        pdf.ln(0.5)
        pdf.set_font(font, size=12, style='B')
        pdf.cell(0, 0.5, _("Invoice To:"), ln=1)
        pdf.set_font(font, size=10)
        pdf.multi_cell(0, 0.5, bill_to)

        # Add table header
        pdf.ln(0.5)
        pdf.set_font(font, size=12, style='B')
        pdf.cell(10 - invoice_padding_left - invoice_padding_right, 0.6, _("Description"), border=1)
        pdf.cell(2.5, 0.6, _("Quantity"), border=1, align="C")
        pdf.cell(2.5, 0.6, _("Unit Price"), border=1, align="C")
        pdf.cell(2.5, 0.6, _("Total"), border=1, align="C")
        pdf.ln()

        # Add table rows
        pdf.set_font(font, size=10)
        for item in items:
            pdf.cell(10 - invoice_padding_left - invoice_padding_right, 0.6, f"{item['description']} ({item['datetime'].strftime('%d.%m.%Y %H:%M')})", border=1)
            pdf.cell(2.5, 0.6, str(item["qty"]), border=1, align="C")
            pdf.cell(2.5, 0.6, f"{item['unit_price']:.2f} {settings.DEFAULT_CURRENCY}", border=1, align="C")
            pdf.cell(2.5, 0.6, f"{item['qty'] * item['unit_price']:.2f} {settings.DEFAULT_CURRENCY}", border=1, align="C")
            pdf.ln()

        # Add totals
        pdf.set_font(font, size=12, style='B')
        pdf.cell(15 - invoice_padding_left - invoice_padding_right, 0.6, _("Subtotal"), border=1)
        pdf.cell(2.5, 0.6, f"{subtotal:.2f} {settings.DEFAULT_CURRENCY}", border=1, align="C")
        pdf.ln()

        pdf.cell(15 - invoice_padding_left - invoice_padding_right, 0.6, _("Tax ({tax_rate}%)").format(tax_rate=tax_rate * 100), border=1)
        pdf.cell(2.5, 0.6, f"{tax:.2f} {settings.DEFAULT_CURRENCY}", border=1, align="C")
        pdf.ln()

        pdf.cell(15 - invoice_padding_left - invoice_padding_right, 0.6, _("Total"), border=1)
        pdf.cell(2.5, 0.6, f"{total:.2f} {settings.DEFAULT_CURRENCY}", border=1, align="C")
        pdf.ln()

        # Add payment instructions
        if self.variant == "advance_payment":
            payment_instructions = self.get_payment_instructions(html=False)

            pdf.ln(1)
            pdf.set_font(font, size=12, style='B')
            pdf.cell(0, 0.6, _("Payment Instructions:"), ln=1)
            pdf.set_font(font, size=10)
            pdf.multi_cell(0, 0.5, payment_instructions)

        return pdf

    def send_confirmation_email(self):
        """
        Send a confirmation email to the user after the order is confirmed.
        """
        if self.status == PaymentStatus.CONFIRMED:
            branding = get_active_branding()
            if branding and branding.invoice_tax_rate:
                site_name = branding.site_name
            else:
                site_name = "Cinema Ticketing"

            if branding and branding.site_url:
                order_link = f"{branding.site_url}{reverse('ticket_list', args=[self.session_id])}"
            else:
                order_link = f"https://example.com/{reverse('ticket_list', args=[self.session_id])}"

            subject = _("Your Invoice for Order {order_id} - {site_name}").format(order_id=self.id, site_name=site_name)
            message = _("Dear Customer,\n\nThank you for your purchase! "
                        "You can find the invoice of your ticket purchase attached.\n\n"
                        "Please find your tickets and purchase details under the following link:\n\n"
                        "{order_link}\n\n"
                        "We look forward to seeing you at the event.\n\n"
                        "Best regards,\nThe Event Team").format(
                            order_link=order_link
                        )
            
            # Generate PDF ticket
            pdf = self.generate_pdf_invoice()
            # Create a BytesIO stream to hold the PDF data
            pdf_output = pdf.output(dest='S')  # Get PDF as a bytearray

            email = EmailMessage(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [self.billing_email]
            )
            email.attach(f"order_invoice_{self.session_id}.pdf", pdf_output, 'application/pdf')
            try:
                email.send()
            except Exception as e:
                logger.error(f"Error sending confirmation email: {e}")
                raise e

    def send_payment_instructions_email(self):
        payment_instructions = self.get_payment_instructions(html=False)

        branding = get_active_branding()
        if branding and branding.invoice_tax_rate:
            site_name = branding.site_name
        else:
            site_name = "Cinema Ticketing"

        if branding and branding.site_url:
            order_link = f"{branding.site_url}{reverse('ticket_list', args=[self.session_id])}"
        else:
            order_link = f"https://example.com/{reverse('ticket_list', args=[self.session_id])}"

        subject = _("Payment Instructions for Your Order {order_id} on {site_name}").format(order_id=self.id, site_name=site_name)

        message = _("Dear Customer,\n\n"
                    "Thank you for your purchase! "
                    "Please find the payment instructions for your order below.\n\n"
                    "{payment_instructions}\n\n"
                    "You can view your order details here: {order_link}\n\n"
                    "We look forward to seeing you at the event.\n\n"
                    "Best regards,\nThe Event Team").format(
                        payment_instructions=payment_instructions,
                        order_link=order_link
                    )
        
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [self.billing_email]
        )
        
        # attach invoice
        pdf = self.generate_pdf_invoice()
        pdf_output = pdf.output(dest='S')
        email.attach(f"order_invoice_{self.session_id}.pdf", pdf_output, 'application/pdf')
        try:
            email.send()
        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")
            raise e
        

        # inform ticket masters emails about new order
        # get all ticket masters emails that are active
        ticket_masters = TicketMaster.objects.filter(is_active=True)

        subject = _("New Order {order_id} on {site_name}").format(order_id=self.id, site_name=site_name)
        message = _("Dear Ticket Master,\n\n"
                    "A new order has been placed on {site_name}.\n\n"
                    "Please find the order details below:\n\n"
                    "Order ID: {order_id}\n"
                    "Order Date: {order_date}\n"
                    "Customer: {customer_name}\n"
                    "Customer Email: {customer_email}\n"
                    "Total Amount: {total_amount} {currency}\n\n"
                    "You can view the order details here: {order_link}\n\n"
                    "Best regards,\nThe Event Team").format(
                        order_id=self.id,
                        site_name=site_name,
                        order_date=self.created.strftime('%Y-%m-%d %H:%M'),
                        customer_name=f"{self.billing_first_name} {self.billing_last_name}",
                        customer_email=self.billing_email,
                        total_amount=self.total,
                        currency=self.currency,
                        order_link=order_link
                    )
        
        recipient_list = [ticket_master.email for ticket_master in ticket_masters]
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list
        )

        email.attach(f"order_invoice_{self.session_id}.pdf", pdf_output, 'application/pdf')
        try:
            email.send()
        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")
            raise e



    # delete order and associated tickets
    def delete(self, *args, **kwargs):

        #if self.status == PaymentStatus.CONFIRMED:
            #if settings.CONFIRM_DELETE_PAID_ORDER or settings.DEBUG:
            #    messages.error(request, _("Cannot delete a paid order."))
            #    return False
        
        # Properly delete associated tickets
        for ticket in self.tickets.all():
            ticket_to_delete = Ticket.objects.get(id=ticket.id)
            ticket_to_delete.delete()
            logger.info(f"Deleted ticket {ticket.id} for event {ticket.event.name}")

        super().delete(*args, **kwargs)


