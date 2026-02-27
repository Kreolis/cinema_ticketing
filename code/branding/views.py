from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import EmailMessage

from django.utils.translation import gettext as _

from .models import Contact
from .forms import ContactForm

import logging

logger = logging.getLogger(__name__)

# contact form view
def contact_form(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            message = form.cleaned_data['message']
            event = form.cleaned_data['event']
            
            contacts = Contact.objects.filter(is_active=True)
            recipient_list = [contact.email for contact in contacts]
            
            message = f'Name: {name}\nEmail: {email}\nEvent: {event}\n\n{message}'

            email = EmailMessage(
                subject=f'Contact Form Submission from {name}',
                body=message,
                from_email=email,
                to=recipient_list,
            )

            try:
                email.send()
            except Exception as e:
                logger.error(f"Error sending confirmation email: {e}")
                raise e
            
            return JsonResponse({"status": "success", 'message': _('Message sent successfully!')})
    else:
        form = ContactForm()

    return render(request, 'contact.html', {'form': form})

