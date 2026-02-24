from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.utils.translation import gettext_lazy as _

from accounting.models import Order
from payments.models import PaymentStatus

class Command(BaseCommand):
    help = _('Delete orders that have timed out')

    def handle(self, *args, **kwargs):
        now = timezone.now()
        waiting_orders = Order.objects.filter(
            status=PaymentStatus.WAITING
        )
        
        first_order = waiting_orders.first()
        if not first_order:
            self.stdout.write(self.style.WARNING('No waiting orders found'))
            return
        
        timed_out_orders = waiting_orders.filter(
            created__lt=now - timedelta(minutes=first_order.timeout)
        )

        count = timed_out_orders.count()
        if count == 0:
            self.stdout.write(self.style.WARNING('No timed-out orders found'))
            return
        
        for order in timed_out_orders:
            self.stdout.write(f'Deleting order {order.id} created at {order.created}')
            order.delete()

        self.stdout.write(self.style.SUCCESS(f'Successfully deleted {count} timed-out orders'))
