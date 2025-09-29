from rest_framework import serializers
from .models import WithdrawalRequest

from django.contrib.auth import get_user_model
User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name',
                  'email', 'photo', 'username', 'phone_number','paypal_email','stripe_account_id']


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    traveler = UserSerializer(read_only=True, many=False, source='user')

    class Meta:
        model = WithdrawalRequest
        fields = ['id',  'amount', 'method', 'message', 'requested_at',
                  'status', 'provider', 'transaction_id', 'error_message', 'processed_by', 'traveler']


class WithdrawalRequestSerializerCreate(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalRequest
        fields = ['id', 'user', 'amount', 'method', 'message', 'requested_at',
                  'status', 'provider', 'transaction_id', 'error_message']
        read_only_fields = ['user', 'status', 'requested_at',
                            'provider', 'transaction_id', 'error_message']

    def validate_amount(self, value):
        user = self.context['request'].user  # get current user
        if value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        if value > user.balance:
            raise serializers.ValidationError("Amount exceeds your current balance.")
        return value
    
    # def validate(self, attrs):
    #     user = self.context['request'].user
    #     # Check if user already has a pending withdrawal
    #     if WithdrawalRequest.objects.filter(user=user, status='pending').exists():
    #         raise serializers.ValidationError(
    #             "You already have a pending withdrawal request."
    #         )
    #     return attrs    