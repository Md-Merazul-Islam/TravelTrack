
from django.shortcuts import redirect
from django.core.mail import send_mail
from apps.notification.utils import create_notification
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from .models import Booking
import paypalrestsdk
from django.contrib.auth import get_user_model
User = get_user_model()

from ..notification.utils import send_notification

# Configure PayPal
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET,
})

class PayPalReturnConfirmView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        payment_id = request.query_params.get("paymentId") or request.query_params.get("payment_id")
        payer_id = request.query_params.get("PayerID") or request.query_params.get("payer_id")
        token = request.query_params.get("token")

        if not payment_id or not payer_id:
            return Response({
                "success": False,
                "error": "Missing PayPal parameters: paymentId and PayerID are required"
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Find the booking
            booking = Booking.objects.filter(transaction_id=payment_id).first()
            if not booking:
                return redirect(f"{settings.FRONTEND_URL}/checkout/paypal/fail/")

            # Check if already paid
            if booking.payment_status == "paid":
                return redirect(f"{settings.FRONTEND_URL}/checkout/paypal/success/")

            # Find PayPal payment
            paypal_payment = paypalrestsdk.Payment.find(payment_id)
            if not paypal_payment:
                return redirect(f"{settings.FRONTEND_URL}/checkout/paypal/fail/")

            # Execute the payment
            if paypal_payment.execute({"payer_id": payer_id}):
                # Update booking status
                booking.payment_status = "paid"
                booking.save(update_fields=["payment_status"])

                # Reduce available space
                service = booking.travel_service
                service.available_space -= booking.package_size
                service.save(update_fields=["available_space"])

                # Send confirmation email (optional)
                try:
                    send_notification(
                        user=booking.user,
                        title="Payment Successful",
                        message=f"Your payment for booking #{booking.orderid} was successful."
                    )
                    send_mail(
                        subject="Payment Confirmed - Your Booking is Complete",
                        message=f"Your booking #{booking.orderid} has been confirmed. Total paid: ${booking.total_cost}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[booking.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    print(f"Email sending failed: {e}")

                # Create notification
                try:
                    create_notification(
                        user=booking.user,
                        title="Payment Successful",
                        message=f"Your payment for booking #{booking.id} was successful.",
                        notification_type="payment_success"
                    )
                except Exception as e:
                    print(f"Notification creation failed: {e}")

                return redirect(f"{settings.FRONTEND_URL}/checkout/paypal/success/")
            else:
                error_msg = paypal_payment.error.get("message", "Payment execution failed")
                return redirect(f"{settings.FRONTEND_URL}/checkout/paypal/fail/")

        except Exception as e:
            print(f"PayPal return error: {e}")
            return redirect(f"{settings.FRONTEND_URL}/checkout/paypal/fail/")
        
        
# views.py
class PayPalCancelView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        payment_id = request.query_params.get("paymentId") or request.query_params.get("payment_id")
        token = request.query_params.get("token")
        
        # Optional: You might want to update the booking status to cancelled
        if payment_id:
            try:
                booking = Booking.objects.filter(transaction_id=payment_id).first()
                if booking and booking.payment_status == "pending":
                    booking.payment_status = "cancelled"
                    booking.save(update_fields=["payment_status"])
            except Exception as e:
                print(f"Error updating cancelled booking: {e}")
        
        return redirect(f"{settings.FRONTEND_URL}/checkout/paypal/cancel/?payment_id={payment_id}")        