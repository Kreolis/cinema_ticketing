from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.template.response import TemplateResponse
from django.core.mail import EmailMessage

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login 
from django.contrib.auth import logout as auth_logout
from django.utils.http import url_has_allowed_host_and_scheme

from django.utils.translation import gettext as _

from .models import Contact
from .forms import ContactForm

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _get_safe_redirect_target(request):
    redirect_candidates = [
        request.POST.get('next'),
        request.GET.get('next'),
        request.META.get('HTTP_REFERER'),
    ]

    for candidate in redirect_candidates:
        if not candidate:
            continue

        if not url_has_allowed_host_and_scheme(
            url=candidate,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            continue

        parsed = urlparse(candidate)
        if parsed.netloc:
            candidate = parsed.path or '/'
            if parsed.query:
                candidate = f'{candidate}?{parsed.query}'

        if candidate == request.path:
            continue

        return candidate

    return None


# create login page
def login(request):
    next_url = _get_safe_redirect_target(request)

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect(next_url or 'event_list')
    else:
        form = AuthenticationForm()
    return TemplateResponse(request, 'login.html', {'form': form, 'next': next_url})

def logout(request):
    next_url = _get_safe_redirect_target(request)
    # Log out the user
    auth_logout(request)
    return redirect(next_url or 'event_list')

def privacy_policy(request):
    return render(request, 'privacy_policy.html')


def terms_of_service(request):
    return render(request, 'terms_of_service.html')

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

