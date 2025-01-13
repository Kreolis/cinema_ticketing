from django import forms
from .models import Payment
from django_recaptcha.fields import ReCaptchaField
from iso3166 import countries
import locale

class PaymentInfoForm(forms.ModelForm):
    #captcha = ReCaptchaField(label="", required=True)
    captcha = forms.CharField(label="Captcha", required=False)

    class Meta:
        model = Payment
        COUNTRY_CHOICES = [(country.alpha2, country.name) for country in countries]
        locale_country_code = locale.getdefaultlocale()[0].split('_')[1].upper()  # Get the default locale country code

        fields = [
            'billing_first_name',  # First name of the billing contact
            'billing_last_name',   # Last name of the billing contact
            'billing_address_1',   # Primary billing address
            'billing_address_2',   # Secondary billing address (optional)
            'billing_city',        # City of the billing address
            'billing_postcode',    # Postcode of the billing address
            'billing_country_code',# Country code of the billing address
            'billing_country_area',# Country area of the billing address
            'billing_email',       # Email address for billing contact
            'captcha',  # ReCaptcha field for spam protection
        ]
        labels = {
            'billing_first_name': 'First Name',
            'billing_last_name': 'Last Name',
            'billing_address_1': 'Address Line 1',
            'billing_address_2': 'Address Line 2',
            'billing_city': 'City',
            'billing_postcode': 'Postcode',
            'billing_country_code': 'Country',
            'billing_country_area': 'State/Province',
            'billing_email': 'Email',
        }
        help_texts = {
            'billing_first_name': 'Enter the first name as it appears on the billing statement.',
            'billing_last_name': 'Enter the last name as it appears on the billing statement.',
            'billing_address_1': 'Enter the primary address for billing purposes.',
            'billing_address_2': 'Enter the secondary address for billing purposes, if any.',
            'billing_city': 'Enter the city for the billing address.',
            'billing_postcode': 'Enter the postcode for the billing address.',
            'billing_country_code': 'Enter the country for the billing address.',
            'billing_country_area': 'Enter the state or province for the billing address.',
            'billing_email': 'Enter the email address where billing information will be sent. If you have not set the send-to-email for each ticket this email will be used for all tickets.',
        }
        widgets = {
            'billing_first_name': forms.TextInput(attrs={'required': True, 'max_length': 30}),
            'billing_last_name': forms.TextInput(attrs={'required': True, 'max_length': 30}),
            'billing_address_1': forms.TextInput(attrs={'required': True, 'max_length': 255}),
            'billing_address_2': forms.TextInput(attrs={'max_length': 255}),
            'billing_city': forms.TextInput(attrs={'required': True, 'max_length': 100}),
            'billing_postcode': forms.TextInput(attrs={'required': True, 'max_length': 20}),
            'billing_country_code': forms.Select(choices=COUNTRY_CHOICES, attrs={'required': True, 'initial': locale_country_code}),
            'billing_country_area': forms.TextInput(attrs={'max_length': 100}),
            'billing_email': forms.EmailInput(attrs={'required': True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['billing_country_code'].initial = self.Meta.locale_country_code

class UpdateEmailsForm(forms.Form):
    email = forms.EmailField(
        label='Email', 
        help_text='Enter the email address where all tickets will be sent to.',
        required=True, 
        widget=forms.EmailInput(attrs={'required': True, 'class': 'form-control'})
    )
