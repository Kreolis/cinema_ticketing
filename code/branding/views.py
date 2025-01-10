from django.shortcuts import render, redirect
from django.core.mail import send_mail

from .models import Contact

# contact form view
def contact_form(request):
    if request.method == 'POST':
        name = request.POST['name']
        email = request.POST['email']
        message = request.POST['message']
        
        contacts = Contact.objects.filter(is_active=True)
        recipient_list = [contact.email for contact in contacts]
        
        send_mail(
            f'Contact Form Submission from {name}',
            message,
            email,
            recipient_list,
            fail_silently=False,
        )
        
        return redirect('contact_success')
    
    return render(request, 'contact.html')

