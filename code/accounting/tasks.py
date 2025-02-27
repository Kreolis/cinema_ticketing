from celery import shared_task
from django.core.management import call_command

@shared_task
def delete_timeout_orders_task():
    call_command('delete_timeout_orders')