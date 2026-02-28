import logging
from celery import shared_task
from .statistics_mail import send_global_statistics_report

logger = logging.getLogger(__name__)

"""
This module defines Celery tasks for the branding app. 
These tasks can be scheduled to run periodically or triggered asynchronously as needed.
"""
@shared_task
def send_global_statistics_report_task():
    return send_global_statistics_report()
