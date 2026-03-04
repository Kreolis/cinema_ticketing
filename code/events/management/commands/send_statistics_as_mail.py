from django.core.management.base import BaseCommand
from django.utils.translation import gettext_lazy as _
from events.statistics_mail import send_global_statistics_report

class Command(BaseCommand):
    help = _('Generate and send global event statistics to mail')

    def handle(self, *args, **kwargs):
        result = send_global_statistics_report()
        self.stdout.write(result)