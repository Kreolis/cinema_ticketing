from django import forms
from events.models import Event  
from django_recaptcha.fields import ReCaptchaField

class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100, 
        required=True, 
        help_text="Enter your full name."
    )
    email = forms.EmailField(
        required=True, 
        help_text="Enter a valid email address."
    )
    message = forms.CharField(
        widget=forms.Textarea, 
        required=True, 
        help_text="Enter your message or inquiry."
    )
    event = forms.ModelChoiceField(
        queryset=Event.objects.all(),
        required=False,
        help_text="Select an event to which your message is related (optional)."
    )
    captcha = ReCaptchaField(
        label="",
        required=True
    )
