from django.contrib import admin
from django.urls import path
from .views import (
    cart_view,
    order_information_form,
    payment_form,
    order_payment,
    order_payment_overview,
    user_confirm_order,
    admin_confirm_order,
    send_confirmation,
    send_invoice,
    refund_order,
    cancel_order,
    send_refund_notification,
    payment_failed,
    ticket_list,
    show_generated_invoice,
    manage_orders,
)

urlpatterns = [
    path('cart/', cart_view, name='cart_view'),
    path('order_information_form/', order_information_form, name='order_information_form'),
    path('payment_form/<str:order_id>', payment_form, name='payment_form'),
    path('order_payment/<str:order_id>', order_payment, name='order_payment'), 
    path('order_payment_overview/', order_payment_overview, name='order_payment_overview'), 
    path('confirm_order/<str:order_id>', user_confirm_order, name='user_confirm_order'), 
    path('payment_failed/', payment_failed, name='payment_failed'),
    path('ticket_list/<str:order_id>', ticket_list, name='ticket_list'),  
    path('order_invoice_<str:order_id>.pdf', show_generated_invoice, name='show_generated_invoice'),
    path('manage_orders/', manage_orders, name='manage_orders'),
    path('admin_confirm_order/<str:order_id>', admin_confirm_order, name='admin_confirm_order'),
    path('send_confirmation/<str:order_id>', send_confirmation, name='send_confirmation'),
    path('send_invoice/<str:order_id>', send_invoice, name='send_invoice'),
    path('refund_order/<str:order_id>', refund_order, name='refund_order'),
    path('send_refund_notification/<str:order_id>', send_refund_notification, name='send_refund_notification'),
    path('cancel_order/<str:order_id>', cancel_order, name='cancel_order'),
]


