from decimal import Decimal
from django.utils.timezone import now
import uuid
from .payments import send_stripe_payout, send_paypal_payout
from django.utils import timezone
from apps.auths.models import CustomUser
from apps.travelers.models import TravelerService
from django.db import models
from django.contrib.auth import get_user_model
User = get_user_model()


class Booking(models.Model):
    PAYMENT_METHODS = (
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
    )

    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )
    ORDER_STATUS = (
        ('pending', 'Pending'),
        ('picked', 'Picked'),          # New status
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('out_for_delivery', 'Out for Delivery'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    )
    ORDER_STATUS_FLOW = {
        # can go to picked first
        'pending': ['picked', 'rejected', 'cancelled'],
        # after picked → in_transit
        'picked': ['in_transit', 'out_for_delivery', 'cancelled'],
        'in_transit': ['out_for_delivery', 'delivered', 'cancelled'],
        'out_for_delivery': ['delivered', 'cancelled'],
        'delivered': [],
        'rejected': [],
        'cancelled': [],
    }
    orderid = models.CharField(max_length=255, blank=True, null=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='bookings', null=True, blank=True)
    travel_service = models.ForeignKey(
        TravelerService, on_delete=models.CASCADE, related_name='bookings')

    shipment_type = models.CharField(max_length=255)
    package_size = models.IntegerField()  # in KG
    
    total_cost = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # Original amount before service charge
    service_charge = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)  # 10% service charge
    
    # sender info
    sender_name = models.CharField(max_length=255)
    sender_address = models.CharField(max_length=255)
    sender_phone_number = models.CharField(max_length=15)
    sender_pickup_date = models.DateField()
    sender_pickup_time = models.TimeField()
    sender_note = models.TextField(blank=True, null=True)
    delivery_type = models.CharField(max_length=255, blank=True, null=True)

    # receiver info
    receiver_name = models.CharField(max_length=255)
    receiver_address = models.CharField(max_length=255)
    receiver_phone_number = models.CharField(max_length=15)
    receiver_note = models.TextField(blank=True, null=True)

    # payment info
    transaction_id = models.CharField(
        max_length=255, blank=True, null=True)  # Stripe PaymentIntent ID
    method = models.CharField(
        max_length=20, choices=PAYMENT_METHODS, default='stripe')
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS, default='pending')

    is_approved = models.BooleanField(default=False)
    order_status = models.CharField(
        max_length=20, choices=ORDER_STATUS, default='pending', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    traveler_approved = models.BooleanField(
        default=False)  # traveler accepted job
    order_completed = models.BooleanField(default=False)  # service delivered

    cancelled_reason = models.TextField(null=True, blank=True)  # reason for cancel

    def __str__(self):
        return f"Booking {self.id} - {self.sender_name} → {self.receiver_name}"

    def save(self, *args, **kwargs):
        if not self.orderid:
            # 14-digit timestamp as orderid
            self.orderid = now().strftime("%Y%m%d%H%M%S")

        # Calculate amounts if not already set
        if not self.base_amount and self.travel_service and self.package_size:
            self.calculate_amounts()
        
        super().save(*args, **kwargs)
        
    def calculate_amounts(self):
        """Calculate base amount, service charge, and total cost"""
        if self.travel_service and self.package_size:
            self.base_amount = self.package_size * self.travel_service.price_per_kg
            self.service_charge = self.base_amount * Decimal('0.10')  # 10% service charge
            self.total_cost = self.base_amount + self.service_charge
            
    def update_status(self, new_status, location=None, note=None):
        if new_status not in [s[0] for s in self.ORDER_STATUS]:
            raise ValueError(f"Invalid status: {new_status}")

        allowed_next = self.ORDER_STATUS_FLOW.get(self.order_status, [])
        if new_status not in allowed_next:
            raise ValueError(
                f"Cannot move from {self.order_status} → {new_status}")

        # Update booking status
        self.order_status = new_status
        if new_status == 'delivered':
            self.order_completed = True
        self.save()

        # Create tracking entry if location provided
        if location:
            BookingTracking.objects.create(
                booking=self,
                status=new_status,
                location=location,
                note=note
            )


class BookingTracking(models.Model):
    booking = models.ForeignKey(
        Booking, on_delete=models.CASCADE, related_name='tracking')
    status = models.CharField(max_length=50)
    location = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.booking.orderid} - {self.status} at {self.location}"


class WithdrawalRequest(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    is_approved = models.BooleanField(default=False)
    processed_by = models.ForeignKey(
        CustomUser, null=True, blank=True, on_delete=models.SET_NULL, related_name='processed_withdrawals'
    )  # admin who approved

    def approve(self, admin_user, method='stripe'):
        if not self.is_approved:
            if self.amount > self.user.balance:
                raise ValueError("Withdrawal amount exceeds user's balance")

            # Send money
            success = False
            if method == 'stripe':
                success = send_stripe_payout(self.user, self.amount)
            elif method == 'paypal':
                success = send_paypal_payout(self.user, self.amount)

            if success:
                self.user.balance -= self.amount
                self.user.save()
                self.is_approved = True
                self.approved_at = timezone.now()
                self.processed_by = admin_user
                self.save()
            else:
                raise ValueError("Payment failed. Try again.")


class DeliveryAcceptRequest(models.Model):
    booking = models.OneToOneField(
        Booking, on_delete=models.CASCADE, related_name="delivery_request"
    )
    customer = models.ForeignKey(
        "auths.CustomUser", on_delete=models.CASCADE, related_name="delivery_requests"
    )
    traveler = models.ForeignKey(
        "auths.CustomUser", on_delete=models.CASCADE, related_name="delivery_travelers"
    )
    request_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),   # admin approved cancel
            ("rejected", "Rejected"),   # admin rejected cancel
        ],
        default="pending",
    )
    rejection_reason = models.TextField(
        null=True, blank=True)  # reason from customer
    cancelled_by_customer = models.BooleanField(
        default=False)  # track who initiated cancel
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request for Booking {self.booking.id} - {self.request_status}"

    def approve(self, admin):
        if self.request_status != "pending":
            raise ValueError("Request already processed")

        booking = self.booking
        traveler = self.traveler

        # Mark booking as delivered
        booking.order_status = "delivered"
        booking.order_completed = True
        booking.save()

        # Update balances
        traveler_share = booking.total_cost * Decimal("0.80")
        traveler.balance += traveler_share
        traveler.save()

        # Admin earnings
        admin_share = booking.total_cost
        admin.balance += admin_share
        admin.save()

        # Update request
        self.request_status = "approved"
        self.save()

        return {
            "traveler_earned": traveler_share,
            "admin_earned": admin_share,
            "status": booking.order_status
        }
