import logging
from celery import shared_task
from .models import Order, PaymentStatus

logger = logging.getLogger(__name__)

"""
This module defines Celery tasks for the accounting app. 
These tasks can be scheduled to run periodically or triggered asynchronously as needed.
"""
@shared_task
def delete_timed_out_orders_task():
    try:
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
