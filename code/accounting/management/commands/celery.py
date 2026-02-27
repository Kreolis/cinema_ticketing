import shlex
import subprocess

from django.core.management.base import BaseCommand
from django.utils import autoreload

from cinema_tickets.settings import DEBUG

import logging

logger = logging.getLogger(__name__)

def restart_celery():
    cmd = 'pkill celery'
    subprocess.call(shlex.split(cmd))
    if DEBUG:
        cmd = 'celery -A cinema_tickets worker --beat --loglevel=debug'
    else:
        cmd = 'celery -A cinema_tickets worker --beat --loglevel=info'
    subprocess.call(shlex.split(cmd))


class Command(BaseCommand):

    def handle(self, *args, **options):
        logger.info('Starting celery worker with autoreload...')

        autoreload.run_with_reloader(restart_celery) 