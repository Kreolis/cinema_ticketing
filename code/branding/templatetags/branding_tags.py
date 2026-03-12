from django import template
from django.urls import reverse
from branding.models import get_active_branding  # Import the class where `get_active_favicon` is defined

register = template.Library()

@register.simple_tag
def get_active_favicon():
    active_branding = get_active_branding()
    return active_branding.favicon.url if active_branding and active_branding.favicon else None

@register.simple_tag
def get_active_logo():
    active_branding = get_active_branding()
    return active_branding.logo.url if active_branding and active_branding.logo else None

@register.simple_tag
def get_active_site_name():
    active_branding = get_active_branding()
    return active_branding.site_name if active_branding and active_branding.site_name else None

@register.simple_tag
def get_privacy_policy_url():
    active_branding = get_active_branding()
    if active_branding and active_branding.privacy_policy_url:
        return active_branding.privacy_policy_url
    return reverse('privacy_policy')

@register.simple_tag
def get_terms_of_service_url():
    active_branding = get_active_branding()
    if active_branding and active_branding.terms_of_service_url:
        return active_branding.terms_of_service_url
    return reverse('terms_of_use')
