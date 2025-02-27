from celery import shared_task
from django.core.management import call_command

@shared_task
def send_statistics_email():
    call_command('send_statistics_as_mail')