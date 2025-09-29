from decimal import Decimal
from django.contrib.auth import get_user_model
from apps.travelers.serializers import TravelerService
from .models import BookingTracking, DeliveryAcceptRequest
import paypalrestsdk
from rest_framework import serializers
from .models import Booking
from django.conf import settings
import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY
User = get_user_model()


class BookingTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingTracking
        fields = ['status', 'location', 'timestamp', 'note']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name',
                  'username', 'email', 'photo']


class TravelerServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TravelerService
        fields = [
            'id', 'user', 'from_address', 'to_address', 'from_date_time', 'to_date_time',
            'available_space', 'price_per_kg', 'description', 'created_at', 'updated_at',
        ]


class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'


class TravelApprovedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ['is_approved']


class StripeBookingSerializer(serializers.ModelSerializer):
    payment_method_id = serializers.CharField(write_only=True)
    # order_status = serializers.CharField(default="pending", read_only=True)

    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = [
            'user', 'transaction_id', 'total_cost', 'base_amount',
            'service_charge', 'method', 'payment_status', 'order_status',
            'orderid', 'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        travel_service = attrs.get("travel_service")
        package_size = attrs.get("package_size")

        if not travel_service:
            raise serializers.ValidationError("Travel service is required.")

        if package_size <= 0:
            raise serializers.ValidationError(
                "Package size must be greater than 0.")

        if package_size > travel_service.available_space:
            raise serializers.ValidationError(
                f"Only {travel_service.available_space}kg available, but you requested {package_size}kg."
            )
        # Calculate amounts with 10% service charge
        base_amount = Decimal(package_size) * travel_service.price_per_kg
        service_charge = base_amount * Decimal('0.10')
        total_cost = base_amount + service_charge

        # Store calculated amounts in context for use in create method
        self.context['calculated_amounts'] = {
            'base_amount': base_amount,
            'service_charge': service_charge,
            'total_cost': total_cost
        }
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        pm_id = validated_data.pop('payment_method_id')
        travel_service = validated_data['travel_service']
        package_size = validated_data['package_size']
        # Get calculated amounts from context
        calculated_amounts = self.context.get('calculated_amounts', {})
        base_amount = calculated_amounts.get('base_amount', 0)
        service_charge = calculated_amounts.get('service_charge', 0)
        total_cost = calculated_amounts.get('total_cost', 0)

        amount = total_cost

        # ---------------- Stripe Customer ----------------
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name() or user.username,
            )
            user.stripe_customer_id = customer.id
            user.save(update_fields=["stripe_customer_id"])
            print(user.stripe_customer_id)
        else:
            customer = stripe.Customer.retrieve(user.stripe_customer_id)

        # ---------------- Attach Payment Method ----------------
        try:
            stripe.PaymentMethod.attach(pm_id, customer=customer.id)
        except stripe.error.CardError as e:
            raise serializers.ValidationError(
                f"Payment method error: {str(e)}")

        # ---------------- Create PaymentIntent ----------------
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # cents
                currency="usd",
                customer=customer.id,
                payment_method=pm_id,
                confirm=True,
                description=f"Booking payment by {user.username}",
                metadata={
                    "user_id": str(user.id),
                    "service_id": str(travel_service.id),
                    "base_amount": str(base_amount),
                    "service_charge": str(service_charge),
                    "total_amount": str(total_cost),
                },
                automatic_payment_methods={
                    "enabled": True,
                    "allow_redirects": "never",
                }
            )

        except stripe.error.StripeError as e:
            raise serializers.ValidationError(f"Stripe error: {str(e)}")

        # ---------------- Save Booking ----------------
        booking = Booking.objects.create(
            user=user,
            transaction_id=intent.id,
            base_amount=base_amount,
            service_charge=service_charge,
            total_cost=total_cost,
            method="stripe",
            payment_status="paid" if intent.status == "succeeded" else "pending",
            order_status="pending",
            **validated_data
        )

        # ✅ Reduce available space if payment succeeded
        if intent.status == "succeeded":
            travel_service.available_space -= package_size
            travel_service.save(update_fields=["available_space"])

        return booking


class PaypalBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = [
            'user', 'transaction_id', 'total_cost', 'base_amount',
            'service_charge', 'method', 'payment_status', 'order_status',
            'orderid', 'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        travel_service = attrs.get("travel_service")
        package_size = attrs.get("package_size")

        if not travel_service:
            raise serializers.ValidationError("Travel service is required.")

        if package_size <= 0:
            raise serializers.ValidationError(
                "Package size must be greater than 0.")

        if package_size > travel_service.available_space:
            raise serializers.ValidationError(
                f"Only {travel_service.available_space}kg available, but you requested {package_size}kg."
            )

        # Calculate amounts with 10% service charge
        base_amount = Decimal(package_size) * travel_service.price_per_kg
        service_charge = base_amount * Decimal('0.10')
        total_cost = base_amount + service_charge

        # Store calculated amounts in context for use in create method
        self.context['calculated_amounts'] = {
            'base_amount': base_amount,
            'service_charge': service_charge,
            'total_cost': total_cost
        }

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        travel_service = validated_data['travel_service']
        package_size = validated_data['package_size']

        # Get calculated amounts from context
        calculated_amounts = self.context.get('calculated_amounts', {})
        base_amount = calculated_amounts.get('base_amount', 0)
        service_charge = calculated_amounts.get('service_charge', 0)
        total_cost = calculated_amounts.get('total_cost', 0)

        # Configure PayPal SDK
        paypalrestsdk.configure({
            "mode": settings.PAYPAL_MODE,
            "client_id": settings.PAYPAL_CLIENT_ID,
            "client_secret": settings.PAYPAL_CLIENT_SECRET,
        })

        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "redirect_urls": {
                "return_url": settings.PAYPAL_RETURN_URL,
                "cancel_url": settings.PAYPAL_CANCEL_URL,
            },
            "transactions": [{
                "amount": {
                    "total": f"{total_cost:.2f}",
                    "currency": "USD",
                    "details": {
                        "subtotal": f"{base_amount:.2f}",
                        "tax": "0.00",
                        "shipping": "0.00",
                        "handling_fee": f"{service_charge:.2f}"
                    }
                },
                "description": f"Booking payment by {user.username}",
                "custom": f"user_id:{user.id},service_id:{travel_service.id}",
                "item_list": {
                    "items": [{
                        "name": f"Package Delivery - {travel_service.id}",
                        "description": f"Package size: {package_size}kg",
                        "quantity": "1",
                        "price": f"{base_amount:.2f}",
                        "currency": "USD"
                    }]
                }
            }],
        })

        if not payment.create():
            error_message = payment.error.get(
                "message", "Unknown PayPal error")
            raise serializers.ValidationError({
                "paypal_error": error_message,
                "details": payment.error.get("details", [])
            })

        approval_url = next(
            (link.href for link in payment.links if link.rel == "approval_url"), None)
        if not approval_url:
            raise serializers.ValidationError("PayPal approval URL not found.")

        booking = Booking.objects.create(
            user=user,
            base_amount=base_amount,
            service_charge=service_charge,
            total_cost=total_cost,
            method="paypal",
            payment_status="pending",
            transaction_id=payment.id,
            **validated_data
        )

        return {
            "booking_id": booking.id,
            "payment_id": payment.id,
            "approval_url": approval_url,
            "base_amount": float(base_amount),
            "service_charge": float(service_charge),
            "total_amount": float(total_cost)
        }

# serializers.py


# class WithdrawalRequestSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = WithdrawalRequest
#         fields = ['id', 'user', 'amount',
#                   'requested_at', 'is_approved', 'approved_at']
#         read_only_fields = ['is_approved', 'approved_at', 'user']

#     def create(self, validated_data):
#         user = self.context['request'].user
#         amount = validated_data['amount']
#         if amount > user.balance:
#             raise serializers.ValidationError(
#                 "Cannot withdraw more than your balance")
#         return WithdrawalRequest.objects.create(user=user, **validated_data)


class DeliveryAcceptRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAcceptRequest
        fields = ['id', 'traveler', 'booking', 'request_status', 'is_accepted']
        read_only_fields = ['is_accepted', 'accepted_at']


class BookingDeliveryAcceptRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryAcceptRequest
        fields = ['id', 'traveler', 'cancelled_by_customer', 'customer', 'request_status', 'created_at']
        read_only_fields = ['traveler', 'customer',
                            'request_status', 'created_at']


class BookingDetailsSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    travel_service = TravelerServiceSerializer(read_only=True)
    tracking = BookingTrackingSerializer(many=True, read_only=True)
    delivery_request = BookingDeliveryAcceptRequestSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'orderid',
            'shipment_type',
            'package_size',
            'total_cost',
            'base_amount',
            'service_charge',
            'sender_name',
            'sender_address',
            'sender_phone_number',
            'sender_pickup_date',
            'sender_pickup_time',
            'sender_note',
            'delivery_type',
            'receiver_name',
            'receiver_address',
            'receiver_phone_number',
            'receiver_note',
            'transaction_id',
            'method',
            'payment_status',
            'traveler_approved',
            'order_completed',
            'order_status',
            'cancelled_reason',
            'created_at',
            'updated_at',
            'user',
            'travel_service',
            'tracking',
            'delivery_request',
        ]


class MyBookingSerializer(serializers.ModelSerializer):
    delivery_request = BookingDeliveryAcceptRequestSerializer(read_only=True)
    service_details = TravelerServiceSerializer(
        read_only=True, many=False, source='travel_service')
    user = UserSerializer(read_only=True)

    class Meta:
        model = Booking
        fields = [
            'id',
            'orderid',
            'shipment_type',
            'package_size',
            'total_cost',
            'base_amount',
            'service_charge',
            'sender_name',
            'sender_address',
            'sender_phone_number',
            'sender_pickup_date',
            'sender_pickup_time',
            'sender_note',
            'delivery_type',
            'receiver_name',
            'receiver_address',
            'receiver_phone_number',
            'receiver_note',
            'transaction_id',
            'method',
            'payment_status',
            'traveler_approved',
            'order_completed',
            'order_status',
            'cancelled_reason',
            'created_at',
            'updated_at',
            'user',
            'travel_service',
            'delivery_request',
            'service_details'
        ]


class DeliveryAcceptRequestSerializer(serializers.ModelSerializer):
    booking = BookingSerializer(read_only=True)
    customer_name = serializers.CharField(
        source="customer.username", read_only=True)
    traveler_name = serializers.CharField(
        source="traveler.username", read_only=True)

    class Meta:
        model = DeliveryAcceptRequest
        fields = [
            "id",
            "booking",
            "customer_name",
            "traveler_name",
            "request_status",
            "rejection_reason",
            "cancelled_by_customer",
            "created_at",
            "updated_at",
        ]
