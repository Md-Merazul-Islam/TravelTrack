from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserProfile, DocumentVerification


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    model = CustomUser
    # Show all important fields in the list view
    list_display = ('email', 'id', 'username', 'role', 'is_verified', 'is_staff',
                    'is_superuser', 'balance', 'phone_number', 'balance', 'stripe_customer_id', 'stripe_account_id','paypal_email','bank_info')
    list_filter = ('role', 'is_verified', 'is_staff', 'is_superuser')
    search_fields = ('email', 'username', 'phone_number',
                     'first_name', 'last_name')
    ordering = ('email',)
    # Allow all fields editable
    fieldsets = None
    add_fieldsets = None


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp', 'otp_created_at',
                    'reset_token', 'reset_token_expires')
    search_fields = ('user__email', 'user__username', 'otp', 'reset_token')
    readonly_fields = ('otp_created_at', 'reset_token_expires')


@admin.register(DocumentVerification)
class DocumentVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'document_type', 'is_verified',
                    'uploaded_at', 'reviewed_at')
    list_filter = ('document_type', 'is_verified')
    search_fields = ('user__email', 'user__username')
    readonly_fields = ('uploaded_at', 'reviewed_at')
