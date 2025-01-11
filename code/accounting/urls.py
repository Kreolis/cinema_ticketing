from django.contrib import admin
from django.urls import path
from .views import (
    cart_view,
    payment_form,  # Add this import
)

urlpatterns = [
    path('cart/', cart_view, name='cart_view'),
    path('payment_form/', payment_form, name='payment_form'),  # Add this URL pattern
]


