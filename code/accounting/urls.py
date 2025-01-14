from django.contrib import admin
from django.urls import path
from .views import (
    cart_view,
    payment_form,
    order_payment_overview,
    confirm_order,
    ticket_list,
)

urlpatterns = [
    path('cart/', cart_view, name='cart_view'),
    path('payment_form/', payment_form, name='payment_form'),
    path('order_payment_overview/', order_payment_overview, name='order_payment_overview'), 
    path('confirm_order/', confirm_order, name='confirm_order'),  
    path('ticket_list/<str:order_id>', ticket_list, name='ticket_list'),  
]


