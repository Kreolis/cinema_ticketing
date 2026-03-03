"""Celery tasks for the events app."""

import logging
from celery import shared_task
from .statistics_mail import send_global_statistics_report

logger = logging.getLogger(__name__)

@shared_task
def send_global_statistics_report_task():
    logger.info("Executing send_global_statistics_report_task.")
    return send_global_statistics_report()
