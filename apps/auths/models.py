from datetime import timedelta
from datetime import timedelta
import string
import random
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
now = timezone.now()
from django.core.exceptions import ValidationError

class Role(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    TRAVELER = 'traveler', 'Traveler'
    SENDER = 'sender', 'Sender'


class CustomUser(AbstractUser):
    email = models.EmailField(unique=True, db_index=True)
    is_verified = models.BooleanField(default=False)
    role = models.CharField(max_length=10, choices=Role.choices,
                            default=Role.TRAVELER, null=True, blank=True, db_index=True)
    address = models.CharField(
        max_length=255, null=True, blank=True, db_index=True)
    phone_number = models.CharField(
        max_length=15, null=True, blank=True, db_index=True)
    photo = models.URLField(blank=True, null=True)
    about = models.TextField(blank=True, null=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # new field
    stripe_customer_id = models.CharField(
        max_length=255, null=True, blank=True, db_index=True
    )
    stripe_account_id = models.CharField(
        max_length=255, null=True, blank=True
    )
    balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00)
    paypal_email = models.EmailField(null=True, blank=True)  # for PayPal
    bank_info = models.TextField(null=True, blank=True) 
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email

    # 🔑 Check if connected to Stripe
    def check_stripe_connected(self):
        if not self.stripe_account_id:
            raise ValidationError(
                "Stripe account not connected for this user.")
        return True

    # 🔑 Check if connected to PayPal
    def check_paypal_connected(self):
        if not self.paypal_email:
            raise ValidationError(
                "PayPal account not connected for this user.")
        return True

    def is_profile_complete(user):
        # Required fields from CustomUser
        required_user_fields = [
            user.first_name,
            user.last_name,
            user.address,
            user.phone_number,
            user.photo,
            user.gender,
            user.date_of_birth,
        ]

        # If any required user field is empty, profile incomplete
        if not all(field not in [None, ""] for field in required_user_fields):
            return False



        # Check if user has at least one verified document
        has_verified_doc = DocumentVerification.objects.filter(
            user=user, is_verified=True
        ).exists()

        if not has_verified_doc:
            return False

        return True


class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_created_at = models.DateTimeField(auto_now_add=True)
    reset_token = models.CharField(max_length=100, null=True, blank=True)
    reset_token_expires = models.DateTimeField(null=True, blank=True)

    def is_otp_expired(self):
        if self.otp_created_at:
            return timezone.now() > self.otp_created_at + timedelta(minutes=10)
        return True

    def is_reset_token_expired(self):
        if self.reset_token_expires:
            return timezone.now() > self.reset_token_expires
        return True

    def generate_reset_token(self):
        self.reset_token = ''.join(random.choices(
            string.ascii_uppercase + string.digits, k=32))
        self.reset_token_expires = timezone.now() + timedelta(minutes=5)
        self.save()
        return self.reset_token

    def is_otp_expired(self):
        if self.otp_created_at:
            return timezone.now() > self.otp_created_at + timezone.timedelta(minutes=10)
        return True

    def __str__(self):
        return f"Profile of {self.user.email}"


class DocumentType(models.TextChoices):
    ID = "id", "ID"
    PASSPORT = "passport", "Passport"
    DRIVING_LICENSE = "driving_license", "Driving License"


class DocumentVerification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    document_type = models.CharField(
        max_length=20, choices=DocumentType.choices)
    front_side = models.URLField(blank=True, null=True)
    back_side = models.URLField(blank=True, null=True)
    is_verified = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.email} - {self.document_type}"
