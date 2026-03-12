import logging
from celery import shared_task
from payments.models import PaymentStatus

logger = logging.getLogger(__name__)

"""
This module defines Celery tasks for the accounting app. 
These tasks can be scheduled to run periodically or triggered asynchronously as needed.
"""
@shared_task
def delete_timed_out_orders_task():
    try:
        from .models import Order

        # Get all orders waiting for payment
        waiting_orders = Order.objects.filter(
            status=PaymentStatus.WAITING
        )
        
        # Filter in Python for those that have timed out
        timed_out_orders_list = [order for order in waiting_orders if order.has_timed_out]
        count = len(timed_out_orders_list)
        
        # If no timed-out orders are found, log the information and return a message
        if count == 0:
            message = "No timed-out orders found"
            logger.info(message)
            return message
        
        # Delete the timed-out orders and log the count
        for order in timed_out_orders_list:
            order.delete()
        
        # Log the successful deletion of timed-out orders
        message = f"Successfully deleted {count} timed-out orders"
        logger.info(message)
        return message
    
    except Exception as e:
        logger.error(f"Error in delete_timed_out_orders_task: {str(e)}")
        raise


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_confirmation_email_task(order_id):
    from .models import Order

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning(f"Skipping confirmation email task: order {order_id} does not exist.")
        return

    order.send_confirmation_email()


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_payment_instructions_email_task(order_id):
    from .models import Order

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning(f"Skipping payment instructions email task: order {order_id} does not exist.")
        return

    order.send_payment_instructions_email()


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_refund_cancel_notification_email_task(order_id):
    from .models import Order

    try:
        order = Order.objects.get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning(f"Skipping refund notification email task: order {order_id} does not exist.")
        return

    order.send_refund_cancel_notification_email()
