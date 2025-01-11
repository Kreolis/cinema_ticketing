from django.shortcuts import render, get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.http import HttpResponse

# django-payments
from payments import get_payment_model, RedirectNeeded
from payments.models import PaymentStatus
from payments.forms import PaymentForm

from .models import Order
from .forms import PaymentInfoForm  # Add this import

def cart_view(request):
    order = get_object_or_404(Order, session_id=request.session.session_key)
    return render(request, 'cart.html', {'order': order})

def payment_form(request):
    order = get_object_or_404(Order, session_id=request.session.session_key)
    if request.method == 'POST':
        form = PaymentInfoForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.order = order
            payment.save()
            return HttpResponse('Payment details submitted successfully.')
    else:
        form = PaymentInfoForm()
    return render(request, 'payment_form.html', {'form': form, 'order': order})