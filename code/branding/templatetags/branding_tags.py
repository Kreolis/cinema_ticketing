from django import template
from branding.models import get_active_branding  # Import the class where `get_active_favicon` is defined

register = template.Library()

@register.simple_tag
def get_active_favicon():
    active_branding = get_active_branding()
    return active_branding.favicon.url if active_branding and active_branding.favicon else None