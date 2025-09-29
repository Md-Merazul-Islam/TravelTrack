# payments.py
from django.utils import timezone
import time
import paypalrestsdk
import stripe
from django.conf import settings

# Initialize payment APIs
stripe.api_key = settings.STRIPE_SECRET_KEY

paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})


def send_stripe_payout(user, amount):
    """
    Send payout to traveler via Stripe Connect
    """
    try:
        if not user.stripe_customer_id:
            raise ValueError("Traveler does not have a Stripe account linked")

        # Convert amount to cents
        amount_in_cents = int(amount * 100)

        payout = stripe.Payout.create(
            amount=amount_in_cents,
            currency="usd",
            destination=user.stripe_customer_id,
            metadata={
                "user_id": str(user.id),
                "purpose": "traveler_payout",
                "amount": str(amount)
            }
        )

        return {
            "success": True,
            "payout_id": payout.id,
            "status": payout.status,
            "amount": amount
        }

    except stripe.error.StripeError as e:
        print(f"Stripe Payout Error: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "stripe_error"
        }
    except Exception as e:
        print(f"Stripe Payout Exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "general_error"
        }


def send_paypal_payout(user, amount):
    if not user.paypal_email:
        return {"success": False, "error": "User has no PayPal account connected"}

    payout = paypalrestsdk.Payout({
        "sender_batch_header": {
            "sender_batch_id": str(user.id) + str(int(timezone.now().timestamp())),
            "email_subject": "You have a payout!",
        },
        "items": [{
            "recipient_type": "EMAIL",
            "amount": {
                "value": str(amount),
                "currency": "USD"
            },
            "receiver": user.paypal_email,
            "note": f"Payout for withdrawal request",
            "sender_item_id": str(user.id)
        }]
    })

    # ⚡ Use async mode
    if payout.create(sync_mode=False):
        batch_id = payout.batch_header.payout_batch_id
        return {"success": True, "payout_batch_id": batch_id}
    else:
        return {"success": False, "error": payout.error}


def send_paypal_refund(transaction_id, amount=None):
    """
    Process PayPal refund
    """
    try:
        payment = paypalrestsdk.Payment.find(transaction_id)
        if not payment:
            raise ValueError("Payment not found on PayPal")

        # Find the sale ID
        sale_id = None
        for transaction in payment.transactions:
            for resource in transaction.related_resources:
                if hasattr(resource, 'sale') and resource.sale:
                    sale_id = resource.sale.id
                    break
            if sale_id:
                break

        if not sale_id:
            raise ValueError("Sale transaction not found in payment")

        # Find the sale
        sale = paypalrestsdk.Sale.find(sale_id)

        # Prepare refund data
        refund_data = {}
        if amount:
            refund_data = {
                "amount": {
                    "total": f"{amount:.2f}",
                    "currency": "USD"
                }
            }

        # Process refund
        refund = sale.refund(refund_data)

        if refund.success():
            return {
                "success": True,
                "refund_id": refund.id,
                "refund_status": refund.state,
                "refund_amount": amount if amount else "full_amount"
            }
        else:
            error_msg = refund.error.get(
                "message", "Unknown PayPal refund error")
            print(f"PayPal Refund Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "error_details": refund.error.get("details", []),
                "error_type": "paypal_refund_error"
            }

    except Exception as e:
        print(f"PayPal Refund Exception: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_type": "general_error"
        }
