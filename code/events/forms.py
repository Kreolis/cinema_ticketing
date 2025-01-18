from django import forms
from django.conf import settings

from django.utils.translation import gettext as _

class TicketSelectionForm(forms.Form):
    def __init__(self, *args, **kwargs):
        price_classes = kwargs.pop('price_classes')
        super().__init__(*args, **kwargs)
        for price_class in price_classes:
            if price_class.notification_message:
                label_text = f"{price_class.name} - {price_class.price} {settings.DEFAULT_CURRENCY} - {price_class.notification_message}"
            else:
                label_text = f"{price_class.name} - {price_class.price} {settings.DEFAULT_CURRENCY}"
            self.fields[f'quantity_{price_class.id}'] = forms.IntegerField(
                label=label_text,
                min_value=0,
                max_value=10,
                initial=0,
                widget=forms.NumberInput(attrs={'class': 'form-control'}),
                help_text="Select the number of tickets for this price class."
            )

    def generate_quick_fill_buttons(self):
        buttons_html = ""
        for field_name in self.fields:
            buttons_html += f"""
            <div class="mb-2">
                <label>{self.fields[field_name].label}</label>
                <div class="quick-fill-buttons">
                    <button type="button" class="btn btn-secondary quick-fill" data-field="{field_name}" data-value="1">{_("+1 Ticket")}</button>
                    <button type="button" class="btn btn-secondary quick-fill" data-field="{field_name}" data-value="2">{_("+2 Tickets")}</button>
                    <button type="button" class="btn btn-secondary quick-fill" data-field="{field_name}" data-value="5">{_("+5 Tickets")}</button>
                </div>
            </div>
            """
        buttons_html += f"""
            <div class="mt-3">
                <button type="button" class="btn btn-danger reset-form">{_("Reset")}</button>
            </div>
        """
        return buttons_html