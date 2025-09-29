from .models import CustomUser, DocumentVerification
from django.contrib.auth import authenticate
from rest_framework import serializers
from django.contrib.auth import get_user_model
User = get_user_model()


class ConnectPaypalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['paypal_email']

    def update(self, instance, validated_data):
        instance.paypal_email = validated_data.get('paypal_email', instance.paypal_email)
        instance.save()
        return instance

class UserSerializerDetails(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone_number",
            "role",
            'is_verified',
            "address",
            "photo",
            "about",
            'bank_info',
            'stripe_customer_id',
            'stripe_account_id',
            'paypal_email'
        ]

class UserSerializerDetailsWithBalance(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone_number",
            "address",
            "photo",
            "about",
            'balance',
            'bank_info',
            'stripe_customer_id',
            'stripe_account_id',
            'paypal_email'
        ]


class DocumentVerificationSerializer(serializers.ModelSerializer):
    user = UserSerializerDetails(read_only=True)

    class Meta:
        model = DocumentVerification
        fields = [
            "id",
            "user",
            "document_type",
            "front_side",
            "back_side",
            "is_verified",
            "uploaded_at",
            "reviewed_at",
        ]
        read_only_fields = ["is_verified",
                            'user', "uploaded_at", "reviewed_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            validated_data["user"] = request.user

        return super().create(validated_data)


class UserRegisterSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = [
            "full_name",
            "email",
            "phone_number",
            "password",
            "role",
            'bank_info',
        ]

    def validate(self, data):
        # Check email unique
        if CustomUser.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError(
                {"email": "Email already exists."})
            
        

        return data

    def create(self, validated_data):
        full_name = validated_data.pop("full_name")
        password = validated_data.pop("password")
        role = validated_data.get("role", "traveler")
        

        # Split full name into first/last
        name_parts = full_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        # Generate unique username
        base_username = (first_name + last_name).lower()
        username = base_username
        counter = 1
        while CustomUser.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        # Create user
        user = CustomUser.objects.create(
            first_name=first_name,
            last_name=last_name,
            username=username,
            **validated_data,
        )
        user.set_password(password)
        user.is_active = False
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        identifier = data['identifier']
        password = data['password']

        # Find user either by username or email
        user = None
        if '@' in identifier and '.' in identifier:
            user = User.objects.filter(email=identifier).first()
        else:
            user = User.objects.filter(username=identifier).first()

        # If the user is not found, raise an error for identifier
        if not user:
            raise serializers.ValidationError(
                {"identifier": "Invalid credentials. Please check your email or username."})

        # Check if the user is active
        if not user.is_active:
            raise serializers.ValidationError(
                {"identifier": "Your account is not active. Please verify your email."})

        # Check password manually and raise an error for password
        if not user.check_password(password):
            raise serializers.ValidationError(
                {"password": "Incorrect password. Please try again."})

        # Authenticate the user with the provided password if the account is active and verified
        user = authenticate(username=user.username, password=password)

        if not user:
            raise serializers.ValidationError(
                "Invalid credentials. Please check your email or password.")

        return {"user": user}


class TokenSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email=value)
            return user
        except User.DoesNotExist:
            raise serializers.ValidationError(
                "User with this email does not exist.")


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    confirm_password = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                "New password and confirmation password do not match.")
        return data


class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField(required=True)
    new_password = serializers.CharField(write_only=True, min_length=6)

class UserSerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField()
    full_name = serializers.CharField(write_only=True, required=False)  # accept full_name input

    
    class Meta:
        model = User
        fields = (
            'id', 'full_name', 'first_name', 'last_name', 'username', 'email', 'gender','date_of_birth',
            'is_verified', 'role', 'address', 'phone_number', 'photo', 'about', 'bank_info', 'document'
        )
        read_only_fields = ('id', 'username', 'email',
                            'is_verified', 'document',)
    
    def create(self, validated_data):
        full_name = validated_data.pop("full_name", "")
        first_name, last_name = self.split_full_name(full_name)
        validated_data['first_name'] = first_name
        validated_data['last_name'] = last_name
        return User.objects.create(**validated_data)

    def update(self, instance, validated_data):
        full_name = validated_data.pop("full_name", None)
        if full_name:
            first_name, last_name = self.split_full_name(full_name)
            validated_data['first_name'] = first_name
            validated_data['last_name'] = last_name
        return super().update(instance, validated_data)

    def split_full_name(self, full_name):
        parts = full_name.strip().split(" ", 1)  # split into max 2 parts
        first_name = parts[0] if len(parts) > 0 else ""
        last_name = parts[1] if len(parts) > 1 else ""
        return first_name, last_name

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    def get_document(self, obj):
        documents = DocumentVerification.objects.filter(user=obj)
        return DocumentVerificationSerializer(documents, many=True).data


class CustomUserAllSerializer(serializers.ModelSerializer):
    document = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'is_active', 'is_verified', 'first_name', 'last_name',
                  'username', 'email', 'role', 'address', 'phone_number', 'photo', 'bank_info', 'about', 'document']

    def get_document(self, obj):
        documents = DocumentVerification.objects.filter(user=obj)
        return DocumentVerificationSerializer(documents, many=True).data
