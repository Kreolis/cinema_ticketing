import os
from django.utils import timezone
from django.db import connection

from celery import Celery
from celery.schedules import crontab

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cinema_tickets.settings')

app = Celery('cinema_tickets')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

def get_active_branding():
    with connection.cursor() as cursor:
        # get active branding form database
        cursor.execute("SELECT * FROM branding_branding WHERE is_active = TRUE")
        row = cursor.fetchone()
        if row:
            print("Active branding found")
            return row
        else:
            print("No active branding found")
    return None

branding = get_active_branding()

default_values = {
    'enable_ticket_statistics_sending': False,
    'ticket_statistics_interval': 24,  # hours
    'ticket_statistics_start': None,  # datetime when email sending should start
    'ticket_statistics_end': None,  # datetime when email sending should end
    'check_timeout_orders_interval': 30  # minutes
}

if branding:
    enable_ticket_statistics_sending = getattr(branding, 'enable_ticket_statistics_sending', default_values['enable_ticket_statistics_sending'])
    statistics_email_interval = getattr(branding, 'ticket_statistics_interval', default_values['ticket_statistics_interval'])
    statistics_email_start = getattr(branding, 'ticket_statistics_start', default_values['ticket_statistics_start'])
    statistics_email_end = getattr(branding, 'ticket_statistics_end', default_values['ticket_statistics_end'])
    check_timeout_orders_interval = getattr(branding, 'check_timeout_orders_interval', default_values['check_timeout_orders_interval'])
else:
    enable_ticket_statistics_sending = default_values['enable_ticket_statistics_sending']
    statistics_email_interval = default_values['ticket_statistics_interval']
    statistics_email_start = default_values['ticket_statistics_start']
    statistics_email_end = default_values['ticket_statistics_end']
    check_timeout_orders_interval = default_values['check_timeout_orders_interval']

app.conf.beat_schedule = {
    'delete-timeout-orders': {
        'task': 'code.accounting.tasks.delete_timeout_orders_task',
        'schedule': crontab(minute='*/%s' % check_timeout_orders_interval),  # every check_timeout_orders_interval minutes
    },
}

if enable_ticket_statistics_sending:
    email_enabled = True
    now = timezone.now()

    if statistics_email_start and statistics_email_start > now:
        email_enabled = False

    if statistics_email_end and statistics_email_end < now:
        email_enabled = False

    if email_enabled:
        app.conf.beat_schedule['send-statistics-email'] = {
            'task': 'code.events.tasks.send_statistics_email',
            'schedule': crontab(minute=0, hour='*/%s' % statistics_email_interval),  # every statistics_email_interval hours
            'args': (statistics_email_start, statistics_email_end),
        }

@app.task(bind=True)                             
def debug_task(self):
    print('Request: {0r}'.format(self.request))