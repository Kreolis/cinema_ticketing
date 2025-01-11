from django import forms

class TicketSelectionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        price_classes = kwargs.pop('price_classes')
        super().__init__(*args, **kwargs)
        for price_class in price_classes:
            self.fields[f'quantity_{price_class.id}'] = forms.IntegerField(
                label=f"{price_class.name} - {price_class.price}",
                min_value=0,
                max_value=10,
                initial=0,
                widget=forms.NumberInput(attrs={'class': 'form-control'}),
                help_text="Select the number of tickets for this price class."
            )