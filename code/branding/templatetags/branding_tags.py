from django import template
from branding.models import Branding  # Import the class where `get_active_favicon` is defined

register = template.Library()

@register.simple_tag
def get_active_favicon():
    active_branding = Branding.objects.filter(is_active=True).first()
    return active_branding.favicon.url if active_branding and active_branding.favicon else None