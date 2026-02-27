import shlex
import subprocess
import os
import signal

from django.core.management.base import BaseCommand
from django.utils import autoreload

from cinema_tickets.settings import DEBUG
from cinema_tickets.settings import FLOWER_USER, FLOWER_PASSWORD

import logging

logger = logging.getLogger(__name__)

# Store the Flower process globally
flower_process = None

def restart_flower():
    global flower_process
    
    # Kill the previous Flower process if it exists
    if flower_process is not None:
        try:
            logger.info(f'Terminating previous Flower process (PID: {flower_process.pid})')
            flower_process.terminate()
            flower_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning(f'Flower process did not terminate gracefully, killing it')
            flower_process.kill()
        except Exception as e:
            logger.error(f'Error terminating Flower process: {e}')
    
    # Start new Flower process
    if DEBUG:
        cmd = f'celery -A cinema_tickets flower --port=5555 --loglevel=debug --basic-auth={FLOWER_USER}:{FLOWER_PASSWORD}'
    else:
        cmd = f'celery -A cinema_tickets flower --port=5555 --loglevel=info --basic-auth={FLOWER_USER}:{FLOWER_PASSWORD}'
    
    logger.info(f'Starting Flower with command: {cmd}')
    flower_process = subprocess.Popen(shlex.split(cmd))


class Command(BaseCommand):

    def handle(self, *args, **options):
        logger.info('Starting flower with autoreload...')

        autoreload.run_with_reloader(restart_flower) 