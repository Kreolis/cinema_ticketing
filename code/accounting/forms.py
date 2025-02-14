from django import forms
from iso3166 import countries
import locale

from django.conf import settings
from django.utils.translation import gettext as _

class PaymentInfoForm(forms.Form):
    billing_first_name = forms.CharField(
        label=_('First Name'),
        help_text=_('Enter the first name as it appears on the billing statement.'),
        widget=forms.TextInput(attrs={'required': True, 'max_length': 30})
    )
    billing_last_name = forms.CharField(
        label=_('Last Name'),
        help_text=_('Enter the last name as it appears on the billing statement.'),
        widget=forms.TextInput(attrs={'required': True, 'max_length': 30})
    )
    billing_address_1 = forms.CharField(
        label=_('Address Line 1'),
        help_text=_('Enter the primary address for billing purposes.'),
        widget=forms.TextInput(attrs={'required': True, 'max_length': 255})
    )
    billing_address_2 = forms.CharField(
        label=_('Address Line 2'),
        help_text=_('Optional: Enter the secondary address for billing purposes, if any.'),
        required=False,
        widget=forms.TextInput(attrs={'max_length': 255})
    )
    billing_city = forms.CharField(
        label=_('City'),
        help_text=_('Enter the city for the billing address.'),
        widget=forms.TextInput(attrs={'required': True, 'max_length': 100})
    )
    billing_postcode = forms.CharField(
        label=_('Postcode'),
        help_text=_('Enter the postcode for the billing address.'),
        widget=forms.TextInput(attrs={'required': True, 'max_length': 20})
    )
    billing_country_code = forms.ChoiceField(
        label=_('Country'),
        help_text=_('Optional: Enter the country for the billing address.'),
        choices=[(country.alpha2, country.name) for country in countries],
        initial=countries.get(locale.getdefaultlocale()[0].split('_')[1].upper()),
        widget=forms.Select(attrs={'required': True})
    )
    billing_country_area = forms.CharField(
        label=_('State/Province'),
        help_text=_('Enter the state or province for the billing address.'),
        required=False,
        widget=forms.TextInput(attrs={'max_length': 100})
    )
    billing_email = forms.EmailField(
        label=_('Email'),
        help_text=_('Enter the email address where billing information will be sent. If you have not set the send-to-email for each ticket this email will be used for all tickets.'),
        widget=forms.EmailInput(attrs={'required': True})
    )

    # enable user to select preferred payment method in settings.PAYMENT_VARIANTS (keys), get human readable names from HUMANIZED_PAYMENT_METHODS (values) 
    payment_method = forms.ChoiceField(
        label=_('Payment Method'),
        help_text=_('Select the payment method you would like to use.'),
        choices=[(key, settings.HUMANIZED_PAYMENT_METHODS[key]) for key in settings.PAYMENT_VARIANTS.keys()],
        widget=forms.Select(attrs={'required': True})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['billing_country_code'].initial = locale.getdefaultlocale()[0].split('_')[1].upper()

class UpdateEmailsForm(forms.Form):
    email = forms.EmailField(
        label=_('Email'), 
        help_text=_('Enter the email address where all tickets will be sent to.'),
        required=True, 
        widget=forms.EmailInput(attrs={'required': True, 'class': 'form-control'})
    )
