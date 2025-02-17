from django import forms
from events.models import Event  
from captcha.fields import CaptchaField
from django.utils.translation import gettext as _

class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100, 
        required=True, 
        help_text=_("Enter your full name.")
    )
    email = forms.EmailField(
        required=True, 
        help_text=_("Enter a valid email address.")
    )
    message = forms.CharField(
        widget=forms.Textarea, 
        required=True, 
        help_text=_("Enter your message or inquiry.")
    )
    event = forms.ModelChoiceField(
        queryset=Event.objects.all(),
        required=False,
        help_text=_("Select an event to which your message is related (optional).")
    )
    captcha = CaptchaField(
        label="",
        required=True
    )
