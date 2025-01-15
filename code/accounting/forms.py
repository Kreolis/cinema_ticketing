from django import forms
from django_recaptcha.fields import ReCaptchaField
from iso3166 import countries
import locale

class PaymentInfoForm(forms.Form):
    billing_first_name = forms.CharField(
        label='First Name',
        help_text='Enter the first name as it appears on the billing statement.',
        widget=forms.TextInput(attrs={'required': True, 'max_length': 30})
    )
    billing_last_name = forms.CharField(
        label='Last Name',
        help_text='Enter the last name as it appears on the billing statement.',
        widget=forms.TextInput(attrs={'required': True, 'max_length': 30})
    )
    billing_address_1 = forms.CharField(
        label='Address Line 1',
        help_text='Enter the primary address for billing purposes.',
        widget=forms.TextInput(attrs={'required': True, 'max_length': 255})
    )
    billing_address_2 = forms.CharField(
        label='Address Line 2',
        help_text='Enter the secondary address for billing purposes, if any.',
        required=False,
        widget=forms.TextInput(attrs={'max_length': 255})
    )
    billing_city = forms.CharField(
        label='City',
        help_text='Enter the city for the billing address.',
        widget=forms.TextInput(attrs={'required': True, 'max_length': 100})
    )
    billing_postcode = forms.CharField(
        label='Postcode',
        help_text='Enter the postcode for the billing address.',
        widget=forms.TextInput(attrs={'required': True, 'max_length': 20})
    )
    billing_country_code = forms.ChoiceField(
        label='Country',
        help_text='Enter the country for the billing address.',
        choices=[(country.alpha2, country.name) for country in countries],
        widget=forms.Select(attrs={'required': True})
    )
    billing_country_area = forms.CharField(
        label='State/Province',
        help_text='Enter the state or province for the billing address.',
        required=False,
        widget=forms.TextInput(attrs={'max_length': 100})
    )
    billing_email = forms.EmailField(
        label='Email',
        help_text='Enter the email address where billing information will be sent. If you have not set the send-to-email for each ticket this email will be used for all tickets.',
        widget=forms.EmailInput(attrs={'required': True})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['billing_country_code'].initial = locale.getdefaultlocale()[0].split('_')[1].upper()

class UpdateEmailsForm(forms.Form):
    email = forms.EmailField(
        label='Email', 
        help_text='Enter the email address where all tickets will be sent to.',
        required=True, 
        widget=forms.EmailInput(attrs={'required': True, 'class': 'form-control'})
    )
