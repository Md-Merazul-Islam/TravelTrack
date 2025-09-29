from apps.bookings.payments import send_paypal_payout, send_stripe_payout
from django.utils import timezone
from django.db import models
from apps.auths.models import CustomUser
import stripe
import paypalrestsdk
from django.conf import settings
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


class WithdrawalRequest(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='withdraw_withdrawals')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    processed_by = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL, related_name='processed_withdraw_withdrawals')
    method = models.CharField(max_length=20, choices=[("stripe", "Stripe"), ("paypal", "PayPal")], default="stripe")
    message = models.TextField(null=True, blank=True)
    # New fields
    provider = models.CharField(max_length=20, choices=[(
        "stripe", "Stripe"), ("paypal", "PayPal")], null=True, blank=True)
    transaction_id = models.CharField(max_length=255, null=True, blank=True)
    # pending, success, failed
    status = models.CharField(max_length=20, default="pending")
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
        
    def approve(self, admin_user):
        if self.is_approved:
            raise ValueError("Already approved")

        if self.amount > self.user.balance:
            raise ValueError("Withdrawal exceeds user balance")

        success = False
        transaction_id = None
        error_message = None
        method = self.method
        
        if method == "stripe":
            if not self.user.stripe_account_id:
                raise ValueError("User has no Stripe account connected")

            amount_in_cents = int(self.amount * 100)
            try:
                transfer = stripe.Transfer.create(
                    amount=amount_in_cents,
                    currency="usd",
                    destination=self.user.stripe_account_id,  # ✅ use account_id
                    description=f"Withdrawal #{self.id}"
                )
                success = True
                transaction_id = transfer.id
            except Exception as e:
                error_message = str(e)

        elif method == "paypal":
            response = send_paypal_payout(self.user, self.amount)
            success = response.get("success", False)
            transaction_id = response.get("payout_batch_id") if success else None
            error_message = response.get("error") if not success else None

        else:
            raise ValueError("Unsupported payout method")

        # Update DB
        if success:
            self.user.balance -= self.amount
            self.user.save()

            self.is_approved = True
            self.approved_at = timezone.now()
            self.processed_by = admin_user
            self.provider = method
            self.transaction_id = transaction_id
            self.status = "success"
            self.save()
            
            #admin user balance
            admin_user.balance -= self.amount
            admin_user.save()

        else:
            self.status = "failed"
            self.error_message = error_message
            self.save()
            raise ValueError(error_message)
