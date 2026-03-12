import logging
from celery import shared_task
from .statistics_mail import send_global_statistics_report

logger = logging.getLogger(__name__)

"""Celery tasks for the events app."""

@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_ticket_email_task(ticket_id):
    from .models import Ticket

    try:
        ticket = Ticket.objects.get(pk=ticket_id)
    except Ticket.DoesNotExist:
        logger.warning(f"Skipping ticket email task: ticket {ticket_id} does not exist.")
        return f"Ticket {ticket_id} does not exist."

    ticket.send_to_email()

    return f"Ticket email sent for ticket {ticket_id} to {ticket.send_to_email}."

@shared_task
def send_global_statistics_report_task():
    logger.info("Executing send_global_statistics_report_task.")
    return send_global_statistics_report()
