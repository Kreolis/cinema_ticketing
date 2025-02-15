from django.core.management.base import BaseCommand
from django.utils import timezone
from accounting.models import Order
from datetime import timedelta
from payments.models import PaymentStatus

class Command(BaseCommand):
    help = 'Delete orders that have timed out'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        timed_out_orders = Order.objects.filter(
            status=PaymentStatus.WAITING,
            has_timed_out=True,
        ) 
        count = timed_out_orders.count()
        timed_out_orders.delete()
        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} timed-out orders'))
