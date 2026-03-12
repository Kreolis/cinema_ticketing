from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta, datetime
from typing import Iterable

from payments.models import BasePayment, PaymentStatus, PurchasedItem
from django.core.mail import EmailMessage
from django.contrib import messages
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

from decimal import Decimal, InvalidOperation
from fpdf import FPDF
import os

from branding.models import get_active_branding
from events.models import Ticket, PriceClass, TicketMaster

import logging

logger = logging.getLogger(__name__)

# service fee types choices
SERVICE_FEE_TYPE_CHOICES = [
    ('fixed_total', _("Fixed Amount on Total")),
    ('percentage_total', _("Percentage on Total")),
    ('fixed_ticket', _("Fixed Amount per Ticket")),
    ('percentage_ticket', _("Percentage per Ticket")),
]

SUPPORTED_PAYMENT_METHOD_CHOICES = [
    ('stripe', _("Stripe (Credit Card)")),
    ('paypal', _("Paypal")),
    ('sofort_klarna', _("Sofort/Klarna")),
    ('advance_payment', _("Advance Payment")),
    ('dummy', _("Dummy Payment")),
]

# class for service fee settings for each payment method
class ServiceFee(models.Model):
    payment_method = models.CharField(max_length=255, 
                                      choices=SUPPORTED_PAYMENT_METHOD_CHOICES,
                                      verbose_name=_("Payment Method"))
    price_classes = models.ManyToManyField(PriceClass, 
                                           verbose_name=_("price classes"), 
                                           related_name="service_fees",
                                           blank=True,
                                           help_text=_("Select the price classes to which this service fee should be applied. If no price class is selected, the service fee will be applied to all tickets sold with the selected payment method.")) 
    display_name = models.CharField(max_length=255, verbose_name=_("Display Name"), 
                                    help_text=_("The name of the service fee that will be displayed to customers during checkout."))
    fee_type = models.CharField(max_length=20, 
                                        choices=SERVICE_FEE_TYPE_CHOICES, 
                                        default='fixed_total', 
                                        help_text=_("Select the type of service fee to apply to ticket sales"))
    fee_amount = models.DecimalField(max_digits=10, 
                                             decimal_places=2, 
                                             default=0, 
                                             help_text=_("Enter the amount of service fee to apply to ticket sales. If type is percentage, enter the percentage (e.g. 5 for 5%)"))

    is_active = models.BooleanField(default=False, help_text=_("Indicates if this service fee is active."))
    
    def save(self, *args, **kwargs):
        logger.info(f"Saving ticket fee: {self.payment_method}, is_active: {self.is_active}")
        super(ServiceFee, self).save(*args, **kwargs)


# class for holding one sessions order until payment is completed
class Order(BasePayment):
    """
    Custom payment model that extends django-payments' BasePayment model
    """
    
    session_id = models.CharField(max_length=255, unique=True)
    tickets = models.ManyToManyField(Ticket, related_name="Tickets")

    timeout = models.IntegerField(default=10)  # in minutes

    # user choices for payment, limit choices to settings.PAYMENT_VARIANTS
    variant = models.CharField(max_length=255, 
                               choices=[(key, key) for key in settings.PAYMENT_VARIANTS.keys()], 
                               verbose_name=_("Payment Method"),
                               default=settings.DEFAULT_PAYMENT_VARIANT)

    currency = models.CharField(max_length=10, default=settings.DEFAULT_CURRENCY)

    failure_url = models.URLField(max_length=255, blank=True, null=True)
    success_url = models.URLField(max_length=255, blank=True, null=True)

    # persisted service fees for display/invoice purposes
    # format: {"<fee_id>": {"display_name": "...", "amount": "12.34"}}
    applied_service_fees_ticket_level = models.JSONField(default=dict, blank=True)
    applied_service_fees_total = models.JSONField(default=dict, blank=True)

    # boolean field to indicate if order is confirmed by the ticket master or not, default is false
    is_confirmed = models.BooleanField(default=False, verbose_name=_("Payment Is Confirmed"), help_text=_("Indicates whether the order has been confirmed by the ticket master."))

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

    def compute_service_fees(self, variant=None):
        store_fees = False
        if variant is None:
            variant = self.variant
            store_fees = True

        tickets = list(self.tickets.select_related("price_class").all())
        
        service_fees_ticket_level = {}
        service_fees_total = {}
    
        # get all services fees applicable for the order's payment method and tickets
        service_fees = ServiceFee.objects.filter(
            is_active=True,
            payment_method=variant,
        ).prefetch_related("price_classes")
        
        # get service fees that are applied on ticket level (fixed amount or percentage per ticket)
        service_fees_applied_to_tickets = [
            fee for fee in service_fees if fee.fee_type in ["fixed_ticket", "percentage_ticket"]
        ]
        # iterate over all tickets in the order and apply service fees on ticket or price class level
        for fee in service_fees_applied_to_tickets:
            fee_amount = Decimal("0")
            applicable_price_class_ids = {price_class.id for price_class in fee.price_classes.all()}
            has_price_class_filter = bool(applicable_price_class_ids)

            for ticket in tickets:
                if has_price_class_filter and ticket.price_class_id not in applicable_price_class_ids:
                    # if fee has price classes assigned and ticket price class is not in it, skip fee for this ticket
                    # or fee is applied to all tickets if no price class is assigned
                    continue
                else:
                    if fee.fee_type == "fixed_ticket":
                        fee_amount += fee.fee_amount
                    elif fee.fee_type == "percentage_ticket":
                        percentage_fee = ticket.price_class.price * (fee.fee_amount / Decimal("100.0"))
                        fee_amount += percentage_fee
            
            service_fees_ticket_level[fee.id] = fee_amount

        subtotal = sum(ticket.price_class.price for ticket in tickets)
        for fee, amount in service_fees_ticket_level.items():
            subtotal += amount

        # calculate service fees that are applied on total level (fixed amount or percentage on total)
        service_fees_applied_to_total = [
            fee for fee in service_fees if fee.fee_type in ["fixed_total", "percentage_total"]
        ]
        for fee in service_fees_applied_to_total:
            if fee.fee_type == "fixed_total":
                fee_amount = fee.fee_amount
            elif fee.fee_type == "percentage_total":
                fee_amount = subtotal * (fee.fee_amount / Decimal("100.0"))
            
            service_fees_total[fee.id] = fee_amount

        if store_fees:
            self.applied_service_fees_ticket_level = self._serialize_service_fees(service_fees_ticket_level)
            self.applied_service_fees_total = self._serialize_service_fees(service_fees_total)
            self.save(update_fields=["applied_service_fees_ticket_level", "applied_service_fees_total"])

        return service_fees_ticket_level, service_fees_total

    def _serialize_service_fees(self, service_fees):
        serialized_service_fees = {}
        for fee, amount in service_fees.items():
            if isinstance(fee, ServiceFee):
                fee_id = fee.id
                display_name = fee.display_name
            else:
                fee_id = fee
                display_name = ServiceFee.objects.filter(id=fee_id).values_list("display_name", flat=True).first()

            if not display_name:
                continue

            serialized_service_fees[str(fee_id)] = {
                "display_name": display_name,
                "amount": str(amount),
            }
        return serialized_service_fees

    def _deserialize_service_fees(self, serialized_service_fees):
        deserialized_service_fees = {}
        for fee_data in (serialized_service_fees or {}).values():
            display_name = fee_data.get("display_name")
            amount_raw = fee_data.get("amount", "0")
            if not display_name:
                continue
            try:
                amount = Decimal(str(amount_raw))
            except (InvalidOperation, TypeError, ValueError):
                amount = Decimal("0")
            deserialized_service_fees[display_name] = deserialized_service_fees.get(display_name, Decimal("0")) + amount
        return deserialized_service_fees

    def _invalidate_applied_service_fees(self):
        self.applied_service_fees_ticket_level = {}
        self.applied_service_fees_total = {}
    
    def get_service_fees(self, variant=None):
        if variant is None:
            if not self.applied_service_fees_ticket_level and not self.applied_service_fees_total:
                self.compute_service_fees()
            return (
                self._deserialize_service_fees(self.applied_service_fees_ticket_level),
                self._deserialize_service_fees(self.applied_service_fees_total),
            )
        else:
            service_fees_ticket_level, service_fees_total = self.compute_service_fees(variant)
            return (
                self._deserialize_service_fees(self._serialize_service_fees(service_fees_ticket_level)),
                self._deserialize_service_fees(self._serialize_service_fees(service_fees_total)),
            )

    def get_total_service_fee_amount(self, variant=None):
        if variant is None:
            service_fees_ticket_level, service_fees_total = self.get_service_fees()
            total_service_fee = sum(service_fees_ticket_level.values()) + sum(service_fees_total.values())
        else:
            service_fees_ticket_level, service_fees_total = self.compute_service_fees(variant)
            total_service_fee = sum(service_fees_ticket_level.values()) + sum(service_fees_total.values())

        return total_service_fee

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
        # check if order is confirmed or not timed out yet
        if self.status == PaymentStatus.CONFIRMED:
            # order is confirmed, so it's valid regardless of timeout
            return True
        if self.created is None or self.modified is None:
            # if created or modified is not set, consider order as invalid to prevent issues with timeout calculation
            return False
        # order is not confirmed, check if it has timed out
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

    def update_tickets(self, new_tickets = None):
        # add new tickets to order
        if new_tickets is not None:
            self.tickets.add(*new_tickets)
        self._invalidate_applied_service_fees()
        # calculate new total amount
        self.total = sum(ticket.price_class.price for ticket in self.tickets.all())  # Sum ticket prices
        self.modified = timezone.now()
        self.save()

    def compute_total(self, with_service_fees = False):
        self.total = sum(ticket.price_class.price for ticket in self.tickets.all())
        if with_service_fees:
            service_fees_ticket_level, service_fees_total = self.compute_service_fees()
            self.total += sum(service_fees_ticket_level.values()) + sum(service_fees_total.values())
        self.save()
        return self.total

    def delete_ticket(self, ticket):
        # remove ticket from order
        self.tickets.remove(ticket)
        # delete ticket
        ticket.delete()
        self._invalidate_applied_service_fees()
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

        # Calculate totals with tax and service fees
        service_fees_ticket_level, service_fees_total = self.get_service_fees()
        items = [{"description": ticket.event.name, "qty": 1, "unit_price": ticket.price_class.price, "datetime": ticket.event.start_time} for ticket in self.tickets.all()]

        fees = []
        for fee_name, amount in service_fees_ticket_level.items():
            fees.append({"description": fee_name, "qty": 1, "unit_price": amount})
        for fee_name, amount in service_fees_total.items():
            fees.append({"description": fee_name, "qty": 1, "unit_price": amount})

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

        # if service fees add spacer row before fees
        if fees:
            pdf.cell(15 - invoice_padding_left - invoice_padding_right, 0.1, "", border=0)
            pdf.ln()

            # add service fees as separate line items in the invoice
            for fee in fees:
                pdf.cell(10 - invoice_padding_left - invoice_padding_right, 0.6, fee["description"], border=1)
                pdf.cell(2.5, 0.6, str(fee["qty"]), border=1, align="C")
                pdf.cell(2.5, 0.6, f"{fee['unit_price']:.2f} {settings.DEFAULT_CURRENCY}", border=1, align="C")
                pdf.cell(2.5, 0.6, f"{fee['qty'] * fee['unit_price']:.2f} {settings.DEFAULT_CURRENCY}", border=1, align="C")
                pdf.ln()

            pdf.cell(15 - invoice_padding_left - invoice_padding_right, 0.1, "", border=0)
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

    def queue_confirmation_email(self):
        if settings.EMAILS_ASYNC:
            from .tasks import send_confirmation_email_task

            transaction.on_commit(lambda: send_confirmation_email_task.delay(self.pk))
            return

        self.send_confirmation_email()

    def send_payment_instructions_email(self):
        payment_instructions = self.get_payment_instructions(html=False)

        # send email to customer with payment instructions and pdf invoice attached
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

        ### Inform ticket masters about new order via email with pdf invoice attached
        # form recipient list 
        recipient_list = []

        # get all email address from users in admin group and superusers and accountant group
        admin_users = User.objects.filter(models.Q(is_superuser=True) | models.Q(groups__name__in=["admin", "Admins"])).distinct()
        accountant_users = User.objects.filter(groups__name__in=["accountant", "Accountants"]).distinct()
        recipient_list.extend(admin_users.values_list('email', flat=True))
        recipient_list.extend(accountant_users.values_list('email', flat=True))
        
        # now add ticket master emails based on location of tickets for events bought in this order
        # inform ticket masters emails about new order
        # get all ticket masters emails that are active
        ticket_masters = TicketMaster.objects.filter(is_active=True)

        # filter ticket master by location and only give access to orders of their location if they have one assigned
        for ticket_master in ticket_masters:
            active_locations = ticket_master.active_locations.all()
            # if ticket master has active locations, check if order contains tickets for events in those locations, 
            # if not skip sending email to this ticket master
            # if ticket master does not have active locations, they should receive email for all orders, so do not skip them
            if active_locations.exists():
                if not self.tickets.filter(event__location__in=active_locations).exists():
                    # if order does not contain tickets for events in ticket masters active locations, skip sending email to this ticket master
                    continue
            recipient_list.append(ticket_master.email)

        # make sure recipient list is unique
        recipient_list = list(set(recipient_list))

        # send email to ticket masters with order details and pdf invoice attached
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

    def queue_payment_instructions_email(self):
        if settings.EMAILS_ASYNC:
            from .tasks import send_payment_instructions_email_task

            transaction.on_commit(lambda: send_payment_instructions_email_task.delay(self.pk))
            return

        self.send_payment_instructions_email()
            

    def send_refund_cancel_notification_email(self):
        branding = get_active_branding()
        if branding and branding.site_name:
            site_name = branding.site_name
        else:
            site_name = "Cinema Ticketing"

        payment_method_display = settings.HUMANIZED_PAYMENT_VARIANT.get(self.variant, self.variant)

        subject = _("Your Order {order_id} has been Refunded or Cancelled - {site_name}").format(order_id=self.id, site_name=site_name)
        message = _("Dear Customer,\n\nWe regret to inform you that your order with ID {order_id} has been refunded or cancelled.\n\n"
                    "If you have already transferred the payment the amount of {total_amount} {currency} will be returned to your original payment method ({payment_method}).\n\n"
                    "Please note that it may take a few business days for the refund to be processed and reflected in your account, depending on your bank or payment provider.\n\n"
                    "If you have any questions or concerns regarding this refund or cancellation, please do not hesitate to contact our support team.\n\n"
                    "Best regards,\nThe Event Team").format(
                        order_id=self.id,
                        total_amount=self.total,
                        currency=self.currency,
                        payment_method=payment_method_display
                    )
        
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [self.billing_email]
        )
        try:
            email.send()
        except Exception as e:
            logger.error(f"Error sending refund notification email: {e}")
            raise e

        ### Inform ticket masters about new order via email with pdf invoice attached
        # form recipient list 
        recipient_list = []

        # get all email address from users in admin group and superusers and accountant group
        admin_users = User.objects.filter(models.Q(is_superuser=True) | models.Q(groups__name__in=["admin", "Admins"])).distinct()
        accountant_users = User.objects.filter(groups__name__in=["accountant", "Accountants"]).distinct()
        recipient_list.extend(admin_users.values_list('email', flat=True))
        recipient_list.extend(accountant_users.values_list('email', flat=True))

        # now add ticket master emails based on location of tickets for events bought in this order
        # inform ticket masters emails about new order
        # get all ticket masters emails that are active
        ticket_masters = TicketMaster.objects.filter(is_active=True)

        # filter ticket master by location and only give access to orders of their location if they have one assigned
        for ticket_master in ticket_masters:
            active_locations = ticket_master.active_locations.all()
            # if ticket master has active locations, check if order contains tickets for events in those locations, 
            # if not skip sending email to this ticket master
            # if ticket master does not have active locations, they should receive email for all orders, so do not skip them
            if active_locations.exists():
                if not self.tickets.filter(event__location__in=active_locations).exists():
                    # if order does not contain tickets for events in ticket masters active locations, skip sending email to this ticket master
                    continue
            recipient_list.append(ticket_master.email)

        # make sure recipient list is unique
        recipient_list = list(set(recipient_list))

        subject = _("Order {order_id} has been Refunded or Cancelled on {site_name}").format(order_id=self.id, site_name=site_name)
        message = _("Dear Ticket Master,\n\nWe inform you that the order with ID {order_id} has been refunded or cancelled.\n\n"
                    "Please find the order details below:\n\n"
                    "Order ID: {order_id}\n"
                    "Order Date: {order_date}\n"
                    "Customer: {customer_name}\n"
                    "Customer Email: {customer_email}\n"
                    "Total Amount: {total_amount} {currency}\n\n"
                    "Best regards,\nThe Event Team").format(
                        order_id=self.id,
                        site_name=site_name,
                        order_date=self.created.strftime('%Y-%m-%d %H:%M'),
                        customer_name=f"{self.billing_first_name} {self.billing_last_name}",
                        customer_email=self.billing_email,
                        total_amount=self.total,
                        currency=self.currency
                    )
        
        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list
        )
        try:
            email.send()
        except Exception as e:
            logger.error(f"Error sending refund notification email: {e}")
            raise e

    def queue_refund_cancel_notification_email(self):
        if settings.EMAILS_ASYNC:
            from .tasks import send_refund_cancel_notification_email_task

            transaction.on_commit(lambda: send_refund_cancel_notification_email_task.delay(self.pk))
            return

        self.send_refund_cancel_notification_email()
        
    def refund_or_cancel(self):
        if self.status not in [PaymentStatus.CONFIRMED, PaymentStatus.PREAUTH]:
            raise Exception(_("Cannot refund or cancel order: order is not in CONFIRMED or PREAUTH status. Current status: {status}").format(status=self.status))
    
        if self.status == PaymentStatus.CONFIRMED:
            super().refund()

            logger.info(f"Order {self.id} has been refunded.")


        if self.status == PaymentStatus.PREAUTH:
            super().release()
    
            logger.info(f"Order {self.id} has been cancelled.")
        
        # delete associated tickets
        tickets_to_delete = list(self.tickets.select_related("event").all())
        for ticket in tickets_to_delete:
            ticket.delete()
            logger.info(f"Deleted ticket {ticket.id} for event {ticket.event.name}")

        self.queue_refund_cancel_notification_email()
        
        return

    # delete order and associated tickets
    def delete(self, *args, **kwargs):

        # Properly delete associated tickets
        all_tickets = list(self.tickets.select_related("event").all())
        for ticket in all_tickets:
            ticket.delete()
            logger.info(f"Deleted ticket {ticket.id} for event {ticket.event.name}")

        super().delete(*args, **kwargs)


