import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
from .models import Booking
import json


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret)
    except ValueError:
        return JsonResponse({"error": "Invalid payload"}, status=400)
    except stripe.error.SignatureVerificationError:
        return JsonResponse({"error": "Invalid signature"}, status=400)

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        booking = Booking.objects.filter(transaction_id=intent["id"]).first()
        if booking:
            booking.payment_status = "paid"
            booking.save(update_fields=["payment_status"])

    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        intent_id = charge["payment_intent"]
        booking = Booking.objects.filter(transaction_id=intent_id).first()
        if booking:
            booking.payment_status = "refunded"
            booking.save(update_fields=["payment_status"])

    return JsonResponse({"status": "ok"})


@csrf_exempt
def paypal_webhook(request):
    event = json.loads(request.body)

    event_type = event.get("event_type")
    resource = event.get("resource")

    if event_type == "PAYMENT.SALE.COMPLETED":
        sale_id = resource["id"]
        booking = Booking.objects.filter(
            transaction_id=resource["parent_payment"]).first()
        if booking:
            booking.payment_status = "paid"
            booking.save(update_fields=["payment_status"])

    elif event_type == "PAYMENT.SALE.REFUNDED":
        booking = Booking.objects.filter(
            transaction_id=resource["parent_payment"]).first()
        if booking:
            booking.payment_status = "refunded"
            booking.save(update_fields=["payment_status"])

    return JsonResponse({"status": "ok"})
