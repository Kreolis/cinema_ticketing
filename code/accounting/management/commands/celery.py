import shlex
import subprocess
import os
import signal

from django.core.management.base import BaseCommand
from django.utils import autoreload

from cinema_tickets.settings import DEBUG

import logging

logger = logging.getLogger(__name__)

# Store the Celery process globally
celery_process = None

def restart_celery():
    global celery_process
    
    # Kill the previous Celery process if it exists
    if celery_process is not None:
        try:
            logger.info(f'Terminating previous Celery process (PID: {celery_process.pid})')
            celery_process.terminate()
            celery_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning(f'Celery process did not terminate gracefully, killing it')
            celery_process.kill()
        except Exception as e:
            logger.error(f'Error terminating Celery process: {e}')
    
    # Start new Celery process
    if DEBUG:
        cmd = 'celery -A cinema_tickets worker --beat --loglevel=debug'
    else:
        cmd = 'celery -A cinema_tickets worker --beat --loglevel=info'
    
    logger.info(f'Starting Celery with command: {cmd}')
    celery_process = subprocess.Popen(shlex.split(cmd))


class Command(BaseCommand):

    def handle(self, *args, **options):
        logger.info('Starting celery worker with autoreload...')

        autoreload.run_with_reloader(restart_celery) 