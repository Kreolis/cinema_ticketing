import logging
from celery import shared_task
from django.core.mail import EmailMessage
from django.conf import settings

from .models import get_active_branding
from events.views import generate_global_statistics_pdf

logger = logging.getLogger(__name__)

"""
This module defines Celery tasks for the branding app. 
These tasks can be scheduled to run periodically or triggered asynchronously as needed.
"""
@shared_task
def send_global_statistics_report_task():
    try:
        active_branding = get_active_branding()
        if not active_branding:
            logger.warning("No active branding found. Skipping global statistics report task.")
            return "No active branding found. Task skipped."
        
        email = active_branding.statistics_email

        if not email:
            logger.warning("No statistics email configured in branding. Skipping global statistics report task.")
            return "No statistics email configured. Task skipped."
        
        # Generate the global statistics PDF
        pdf = generate_global_statistics_pdf()
        
        # Prepare email
        site_name = active_branding.site_name if active_branding.site_name else "Cinema Ticketing"
        subject = f"Global Statistics Report - {site_name}"
        message = f"Dear Administrator,\n\nPlease find attached the global statistics report for {site_name}.\n\nBest regards,\nSystem"
        
        # Create email with PDF attachment
        email_message = EmailMessage(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email]
        )
        
        # Attach the PDF
        pdf_output = pdf.output(dest='S')  # Get PDF as a bytearray
        email_message.attach("global_statistics_report.pdf", pdf_output, 'application/pdf')
        
        # Send email
        try:
            email_message.send()
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return f"Failed to send email: {str(e)}"
        
        logger.info(f"Global statistics report sent successfully to {email}.")
        return f"Global statistics report sent successfully to {email}."
    
    except Exception as e:
        logger.error(f"Error in send_global_statistics_report_task: {str(e)}")
        return f"Error in send_global_statistics_report_task: {str(e)}"
