from payments import PaymentStatus, BasePaymentProvider

class AdvancePaymentProvider(BasePaymentProvider):
    def get_form(self, payment, data=None):
        # Implement the form for advance payment
        pass

    def process_data(self, payment, request):
        # Implement the logic to process the payment data
        pass

    def capture(self, payment, amount=None):
        # Implement the logic to capture the payment
        payment.change_status(PaymentStatus.CONFIRMED)

    def release(self, payment):
        # Implement the logic to release the payment
        payment.change_status(PaymentStatus.REFUNDED)

    def refund(self, payment, amount=None):
        # Implement the logic to refund the payment
        payment.change_status(PaymentStatus.REFUNDED)

