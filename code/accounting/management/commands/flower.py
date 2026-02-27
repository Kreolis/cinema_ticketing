import shlex
import subprocess

from django.core.management.base import BaseCommand
from django.utils import autoreload

from cinema_tickets.settings import DEBUG
from cinema_tickets.settings import FLOWER_USER, FLOWER_PASSWORD

import logging

logger = logging.getLogger(__name__)

def restart_flower():
    cmd = 'pkill flower'
    subprocess.call(shlex.split(cmd))
    if DEBUG:
        cmd = f'celery -A cinema_tickets flower --port=5555 --loglevel=debug --basic-auth={FLOWER_USER}:{FLOWER_PASSWORD}'
    else:
        cmd = f'celery -A cinema_tickets flower --port=5555 --loglevel=info --basic-auth={FLOWER_USER}:{FLOWER_PASSWORD}'
    subprocess.call(shlex.split(cmd))


class Command(BaseCommand):

    def handle(self, *args, **options):
        logger.info('Starting flower with autoreload...')

        autoreload.run_with_reloader(restart_flower) 