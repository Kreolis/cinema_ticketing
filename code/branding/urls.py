from django.urls import path
from .views import (
    contact_form,
    privacy_policy,
    terms_of_service,
)

urlpatterns = [
    path('privacy-policy', privacy_policy, name='privacy_policy'),
    path('terms-of-service', terms_of_service, name='terms_of_service'),
    path('contact', contact_form, name='contact_form'),  # Front page URL
]