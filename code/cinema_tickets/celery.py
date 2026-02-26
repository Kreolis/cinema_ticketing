import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cinema_tickets.settings')

app = Celery('cinema_tickets')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Define periodic tasks using Celery beat
app.conf.beat_schedule = {
    'delete_timed_out_orders_task-every-600-seconds': {
        'task': 'accounting.tasks.delete_timed_out_orders_task',
        'schedule': 600.0,
    },
}

# Set the timezone for Celery
app.conf.timezone = 'UTC'

# Add a debug task for testing purposes
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')


