from django.contrib import admin
from django.urls import path
from .views import (
    payment_create,
    payment_confirmation,
    payment_details,
)
 
urlpatterns = [
    path('create/<int:payment_id>/', payment_create, name='payment_create'),
    path('details/<int:payment_id>/', payment_details, name='payment_details'),
    path('confirmation/<int:payment_id>/', payment_confirmation, name='payment_confirmation'),
]


