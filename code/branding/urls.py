from django.urls import path
from .views import (
    contact_form,
    privacy_policy,
    terms_of_use,
)

urlpatterns = [
    path('privacy-policy', privacy_policy, name='privacy_policy'),
    path('terms-of-use', terms_of_use, name='terms_of_use'),
    path('contact', contact_form, name='contact_form'),  # Front page URL
]