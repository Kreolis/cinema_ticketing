from payments import PaymentStatus
from payments import RedirectNeeded
from payments.core import BasicProvider
from payments import RedirectNeeded

from django.http import HttpResponseRedirect

class AdvancePaymentProvider(BasicProvider):
    """
    A custom payment provider for handling advance payments.
    This provider gives the possibility for the user to transfer the money via bank transfer. 
    The payment requires manual verification by the admin, which can be done in the Django admin interface.
    """
    def get_form(self, payment, data=None):
        # there is no form needed as everything is handled via users own bank transfer and manual verification, 
        # (biiling info is collected in a separate form before the payment process starts)
        # but we need to return a form for the payment process to work

        if payment.status == PaymentStatus.WAITING:
            payment.change_status(PaymentStatus.PREAUTH)
            raise RedirectNeeded(payment.get_success_url())
        
        raise RedirectNeeded(payment.get_failure_url())

    def process_data(self, payment, request):
        if payment.status in [PaymentStatus.CONFIRMED, PaymentStatus.PREAUTH]:
            payment.captured_amount = payment.total
            return HttpResponseRedirect(payment.get_success_url())
        return HttpResponseRedirect(payment.get_failure_url())

    def capture(self, payment, amount=None):
        payment.change_status(PaymentStatus.CONFIRMED)
        payment.captured_amount = amount or payment.total
        return amount

    def release(self, payment):
        # Implement the logic to release the payment
        payment.change_status(PaymentStatus.REFUNDED)
        return None

    def refund(self, payment, amount=None):
        # Implement the logic to refund the payment
        payment.change_status(PaymentStatus.REFUNDED)
        return amount or 0
    