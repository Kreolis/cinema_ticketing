from django import forms
from .models import Payment

from decimal import Decimal

class PaymentInfoForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'billing_first_name',
            'billing_last_name',
            'billing_address_1',
            'billing_address_2',
            'billing_city',
            'billing_postcode',
            'billing_country_code',
            'billing_country_area',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Prefilled and non-editable fields
        #self.fields['description'].initial = 'Ticket Purchase'
        #self.fields['description'].disabled = True

        #self.fields['total'].initial = Decimal(120)
        #self.fields['total'].disabled = True

        #self.fields['tax'].initial = Decimal(20)
        #self.fields['tax'].disabled = True

        #self.fields['currency'].initial = 'EUR'
        #self.fields['currency'].disabled = True

        #self.fields['delivery'].initial = Decimal(10)
        #self.fields['delivery'].disabled = True