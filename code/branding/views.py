from django.shortcuts import render
from django.http import JsonResponse
from django.core.mail import send_mail

from django.utils.translation import gettext as _

from .models import Contact
from .forms import ContactForm

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

            send_mail(
                f'Contact Form Submission from {name}',
                message,
                email,
                recipient_list,
                fail_silently=False,
            )
            
            return JsonResponse({"status": "success", 'message': _('Message sent successfully!')})
    else:
        form = ContactForm()

    return render(request, 'contact.html', {'form': form})

