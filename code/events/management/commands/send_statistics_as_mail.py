from django.core.management.base import BaseCommand
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

from branding.models import get_active_branding
from events.views import generate_global_statistics_pdf


class Command(BaseCommand):
    help = _('Generate and send global event statistics to mail')

    def handle(self, *args, **kwargs):
        branding = get_active_branding()

        if not branding:
            self.stdout.write(self.style.ERROR('No active branding found'))

        if not branding.enable_ticket_statistics_sending:
            self.stdout.write(self.style.SUCCESS('Ticket statistics sending is disabled'))
            return
        
        if not branding.ticket_statistics_email:
            self.stdout.write(self.style.ERROR('No email address for ticket statistics found'))
            return
        
        if branding:
            site_name = branding.site_name
        else:
            site_name = "Cinema Ticketing"

        pdf = generate_global_statistics_pdf()
        # Create a BytesIO stream to hold the PDF data
        pdf_output = pdf.output(dest='S')  # Get PDF as a bytearray

        subject = _('All Events Statistics - {site_name}').format(
            site_name=site_name
        )
        message = _('Attached you will find the all event statistics for the last {interval} hours.').format(
            interval=branding.ticket_statistics_interval
        )
        
        # send the email
        email = EmailMessage(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [branding.ticket_statistics_email],
            )
        
        now = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
        email.attach(f'all_event_statistics_{site_name}_{now}.pdf', pdf_output, 'application/pdf')

        try:
            email.send()
        except Exception as e:
            # Log the error or handle it as needed
            self.stdout.write(self.style.ERROR('Failed to send global event statistics'))
            self.stdout.write(self.style.ERROR(e))
        else:
            self.stdout.write(self.style.SUCCESS('Successfully sent global event statistics'))
            