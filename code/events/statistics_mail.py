import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from branding.models import get_active_branding
from events.views import generate_global_statistics_pdf


logger = logging.getLogger(__name__)


def send_global_statistics_report():
    try:
        branding = get_active_branding()

        if not branding:
            logger.error("No active branding found. Cannot send global statistics report.")
            return "No active branding found."

        if not branding.enable_ticket_statistics_sending:
            logger.info("Ticket statistics sending is disabled. Skipping sending global statistics report.")
            return "Ticket statistics sending is disabled."

        if not branding.ticket_statistics_email:
            logger.error("No email address for ticket statistics found. Cannot send global statistics report.")
            return "No ticket statistics email configured."

        site_name = branding.site_name or "Cinema Ticketing"

        pdf = generate_global_statistics_pdf()
        pdf_output = pdf.output(dest='S')

        subject = _('All Events Statistics - {site_name}').format(site_name=site_name)
        message = _('Attached you will find the all event statistics for the last {interval} hours.').format(
            interval=branding.ticket_statistics_interval
        )

        email = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [branding.ticket_statistics_email],
        )

        now = timezone.now().strftime('%Y-%m-%d_%H-%M-%S')
        email.attach(f'all_event_statistics_{site_name}_{now}.pdf', pdf_output, 'application/pdf')
        email.send()

        success_message = f"Global statistics report sent successfully to {branding.ticket_statistics_email}."
        logger.info(success_message)
        return success_message

    except Exception as error:
        error_message = f"Error in send_global_statistics_report: {error}"
        logger.error(error_message)
        return error_message
