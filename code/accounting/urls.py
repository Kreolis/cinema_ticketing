from django.contrib import admin
from django.urls import path
from .views import (
    cart_view,
    payment_form,
    order_payment_overview,
    confirm_order,
    admin_confirm_order,
    send_confirmation,
    send_invoice,
    payment_failed,
    ticket_list,
    show_generated_invoice,
    manage_orders,
    login,
    logout
)

urlpatterns = [
    path('cart/', cart_view, name='cart_view'),
    path('payment_form/', payment_form, name='payment_form'),
    path('order_payment/<str:order_id>', order_payment_overview, name='order_payment'), 
    path('order_payment_overview/', order_payment_overview, name='order_payment_overview'), 
    path('confirm_order/<str:order_id>', confirm_order, name='confirm_order'), 
    path('payment_failed/', payment_failed, name='payment_failed'),
    path('ticket_list/<str:order_id>', ticket_list, name='ticket_list'),  
    path('order_invoice_<str:order_id>.pdf', show_generated_invoice, name='show_generated_invoice'),
    path('manage_orders/', manage_orders, name='manage_orders'),
    path('admin_confirm_order/<str:order_id>', admin_confirm_order, name='admin_confirm_order'),
    path('send_confirmation/<str:order_id>', send_confirmation, name='send_confirmation'),
    path('send_invoice/<str:order_id>', send_invoice, name='send_invoice'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout')
]


