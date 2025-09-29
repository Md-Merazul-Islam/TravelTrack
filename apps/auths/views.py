
from apps.core.response import success_response, failure_response
from rest_framework import generics
from ..core.response import failure_response, success_response
from rest_framework import viewsets, permissions, status
from ..core.pagination import CustomPagination
from .models import CustomUser, DocumentVerification
from django.db import transaction
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.db.models import Q
import os
from rest_framework.pagination import PageNumberPagination
import random
from django.utils import timezone
from django.contrib.auth import login, get_user_model, update_session_auth_hash
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UserProfile
from rest_framework import viewsets, permissions
from .serializers import (
    UserRegisterSerializer, LoginSerializer, UserSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer, PasswordChangeSerializer, CustomUserAllSerializer,
    DocumentVerificationSerializer,ConnectPaypalSerializer,UserSerializerDetailsWithBalance
)
from .tokens import email_activation_token
from rest_framework.authentication import TokenAuthentication
from apps.core.response import failure_response, success_response
BASE_URL = os.getenv('BASE_URL')
User = get_user_model()


class ConnectPaypalView(generics.UpdateAPIView):
    serializer_class = ConnectPaypalSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
    def update(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = self.get_serializer(user, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response("Paypal connected successfully", serializer.data)

class DetailSingleProfileWithBalance(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializerDetailsWithBalance
    
    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response("Profile retrieved successfully", serializer.data)

class DetailSingleProfile(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'id'

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response("Profile retrieved successfully", serializer.data)


class ProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        data = request.data
        # Proceed with the regular update logic
        serializer = self.get_serializer(
            instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return success_response("Profile updated successfully", serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success_response("Profile retrieved successfully", serializer.data)


class RegisterAPIView(APIView):
    serializer_class = UserRegisterSerializer

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid():
            user = serializer.save()

            # Generate OTP
            otp = str(random.randint(100000, 999999))

            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.otp = otp
            profile.otp_created_at = timezone.now()
            profile.save()

            # Send OTP via email
            subject = "Your OTP Code"
            text_body = f"Your OTP is {otp}"
            html_body = f"""
            <p>Your verification OTP is:</p>
            <h2 style="font-size:28px; color:#2c3e50;">{otp}</h2>
            <p>It will expire in 10 minutes.</p>
            """

            email = EmailMultiAlternatives(subject, text_body, to=[user.email])
            email.attach_alternative(html_body, "text/html")
            email.send()
            return success_response("OTP sent to your email. Please verify.", {"email": user.email})

        return failure_response("Something went wrong.", serializer.errors)


class VerifyOTPAPIView(APIView):
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        try:
            user = CustomUser.objects.get(email=email)
            profile = user.userprofile
        except CustomUser.DoesNotExist:
            return failure_response("Invalid email.", {})

        # Check OTP
        if profile.is_otp_expired():
            return failure_response("OTP expired. Please request a new one.", {})

        if profile.otp != otp:
            return failure_response("Invalid OTP.", {})

        # Mark user as verified
        user.is_active = True
        user.is_verified = True
        user.save()

        profile.otp = None  # clear otp
        profile.save()

        return success_response("Account verified successfully.", {"email": user.email})


class ResendOTPAPIView(APIView):
    def post(self, request):
        email = request.data.get("email")

        try:
            user = CustomUser.objects.get(email=email)
            profile = user.userprofile
        except CustomUser.DoesNotExist:
            return failure_response("Invalid email.", {})

        otp = str(random.randint(100000, 999999))
        profile.otp = otp
        profile.otp_created_at = timezone.now()
        profile.save()

        email_subject = "Resend OTP Code"
        email_body = f"Your new OTP is: {otp}. It will expire in 10 minutes."
        email_obj = EmailMultiAlternatives(
            email_subject, email_body, to=[user.email]
        )
        email_obj.send()

        # ✅ return the string email, not the object
        return success_response("A new OTP has been sent to your email.", {"email": user.email})


class ResendVerificationEmailAPIView(APIView):
    """
    This view allows users to request a resend of the verification email if they
    haven't received it or missed it.
    """

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')

        if not email:
            return Response(
                {'error': 'Email is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = get_object_or_404(User, email=email)

        if user.is_verified:
            return Response(
                {'message': 'User is already verified.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.is_active:
            return Response(
                {'message': 'User is already active.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate token and uid for verification link
        token = email_activation_token.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        confirm_link = f"{BASE_URL}/api/v1/auth/active/{uid}/{token}/"
        email_subject = "Confirm Your Email"
        email_body = render_to_string(
            'confirm_email.html', {'confirm_link': confirm_link})

        email = EmailMultiAlternatives(email_subject, '', to=[user.email])
        email.attach_alternative(email_body, "text/html")

        email.send()

        return Response(
            {'success': True, 'message': 'Verification email has been resent. Please check your email.'},
            status=status.HTTP_200_OK
        )


class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(self, user):
        refresh_token = super().for_user(user)

        # Add custom claims
        refresh_token.payload['username'] = user.username
        refresh_token.payload['email'] = user.email
        refresh_token.payload['role'] = user.role

        return refresh_token


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']

            refresh = CustomRefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            response = Response({
                'success': True,
                'statusCode': status.HTTP_200_OK,
                'message': 'Login successful',
                'data': {
                    "user_id": user.id,
                    'username': user.username,
                    'role': user.role,
                    'is_complete': user.is_profile_complete(),
                    'access': access_token,
                    'refresh': refresh_token,
                }
            })

            response.set_cookie('refresh_token', refresh_token,
                                httponly=True, secure=True)

            login(request, user)
            return response

        first_error_message = next(iter(serializer.errors.values()))[0]
        return Response({
            'success': False,
            'statusCode': status.HTTP_400_BAD_REQUEST,
            'message': first_error_message,
            'error': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ProtectedView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(
            message="You have access!",
            data={},
            status_code=status.HTTP_200_OK
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()

                response = success_response("Logout successful")
                # Delete the refresh token cookie
                response.delete_cookie('refresh_token')
                return response
            return failure_response("Refresh token not provided")
        except Exception as e:
            return failure_response("Logout failed", str(e), status.HTTP_400_BAD_REQUEST)


class GetNewAccessTokenView(APIView):
    """Get new access token section."""
    permission_classes = [AllowAny]
    authentication_classes = [TokenAuthentication]

    def post(self, request):
        refresh_token = request.data.get('refresh')

        if not refresh_token:
            return Response(
                {"detail": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate and create a new access token
            new_access = RefreshToken(refresh_token).access_token
            return Response(
                {"access": str(new_access)},
                status=status.HTTP_200_OK
            )
        except TokenError:
            return Response(
                {"detail": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED
            )


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        # Check if the old password is correct
        if not user.check_password(old_password):
            return failure_response("Incorrect old password", {"detail": "Incorrect old password"}, status.HTTP_400_BAD_REQUEST)

        # Update password
        user.set_password(new_password)
        user.save()

        # Update session to prevent logout after password change
        update_session_auth_hash(request, user)

        return success_response({"message": "Password changed successfully"}, status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    """Send OTP to user's email for password reset"""

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return failure_response({"message": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Generate a random OTP of 6 digti
        otp = str(random.randint(100000, 999999))

        # Save OTP in user profile
        user_profile, _ = UserProfile.objects.get_or_create(user=user)
        user_profile.otp = otp
        user_profile.otp_created_at = timezone.now()
        user_profile.save()

        # Send OTP email
        email_subject = "Your OTP for Password Reset"
        email_body = render_to_string(
            'reset_password_email.html', {'otp': otp})
        email = EmailMultiAlternatives(email_subject, '', to=[user.email])
        email.attach_alternative(email_body, "text/html")
        email.send()

        return success_response("Please check your email for OTP.", {user.email}, status.HTTP_200_OK)


class ValidateOTPView(APIView):
    """Validate OTP and return reset token"""

    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')

        try:
            user_profile = UserProfile.objects.get(user__email=email)
        except UserProfile.DoesNotExist:
            return failure_response({"message": "User with this email does not exist."}, status=status.HTTP_404_NOT_FOUND)

        # Check if OTP matches and is not expired
        if user_profile.otp == otp:
            if user_profile.is_otp_expired():
                return failure_response({"message": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

            # Generate reset token
            reset_token = user_profile.generate_reset_token()

            return success_response(
                "Successfully OTP Verified. Proceed with password reset.",
                {"reset_token": reset_token},
                status.HTTP_200_OK
            )

        return failure_response({"message": "Invalid OTP."}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    """Reset password using reset token (only token and password required)"""

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']

        try:
            user_profile = UserProfile.objects.get(reset_token=reset_token)
        except UserProfile.DoesNotExist:
            return failure_response({"message": "Invalid reset token."}, status=status.HTTP_400_BAD_REQUEST)

        # Check if token is expired
        if user_profile.is_reset_token_expired():
            return failure_response({"message": "Reset token has expired."}, status=status.HTTP_400_BAD_REQUEST)

        # Reset password
        user = user_profile.user
        user.set_password(new_password)
        user.save()

        # Clear all reset data
        user_profile.otp = None
        user_profile.reset_token = None
        user_profile.reset_token_expires = None
        user_profile.save()

        return success_response("Password reset successfully.", {}, status.HTTP_200_OK)


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class AllUsers(viewsets.ModelViewSet):
    queryset = User.objects.filter().order_by('-id')
    serializer_class = CustomUserAllSerializer
    permission_classes = [permissions.IsAdminUser]
    pagination_class = CustomPagination

    # GET - Retrieve List of Active Users
    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return success_response("User list retrieved successfully", serializer.data)
        except Exception as e:
            return failure_response("Failed to retrieve user list", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # POST - Create a New User
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return success_response("User created successfully", serializer.data, status.HTTP_201_CREATED)
            return failure_response("User creation failed", serializer.errors)
        except Exception as e:
            return failure_response("An error occurred while creating the user", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # GET - Retrieve a Single User
    def retrieve(self, request, pk=None):
        try:
            user = get_object_or_404(User, pk=pk)
            serializer = self.get_serializer(user)
            return success_response("User details retrieved successfully", serializer.data)
        except Exception as e:
            return failure_response("Failed to retrieve user details", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # PUT - Update a User
    def update(self, request, pk=None):
        try:
            user = get_object_or_404(User, pk=pk)
            serializer = self.get_serializer(
                user, data=request.data, partial=False)
            if serializer.is_valid():
                serializer.save()
                return success_response("User updated successfully", serializer.data)
            return failure_response("User update failed", serializer.errors)
        except Exception as e:
            return failure_response("An error occurred while updating the user", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # PATCH - Partially Update a User
    def partial_update(self, request, pk=None):
        try:
            user = get_object_or_404(User, pk=pk)
            serializer = self.get_serializer(
                user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return success_response("User partially updated successfully", serializer.data)
            return failure_response("User partial update failed", serializer.errors)
        except Exception as e:
            return failure_response("An error occurred while partially updating the user", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)

    # DELETE - Deactivate a User (Soft Delete)
    def destroy(self, request, pk=None):
        try:
            user = get_object_or_404(User, pk=pk)
            user.is_active = False  # Soft delete instead of hard delete
            user.save()
            return success_response("User deactivated successfully", None, status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return failure_response("Failed to deactivate user", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckEmailOrCreateUser(APIView):

    def post(self, request):
        email = request.data.get("email")
        name = request.data.get("name")

        if not email or not name:
            return Response({"error": "Email and name is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the email exists
        user = User.objects.filter(Q(email=email) | Q(username=email)).first()

        if user:
            # If the user exists, generate JWT tokens with custom claims
            refresh = CustomRefreshToken.for_user(
                user)  # Using the custom token class
            refresh_token = str(refresh)
            access_token = str(refresh.access_token)

            return Response({
                "success": True,
                "statusCode": status.HTTP_200_OK,
                "message": "Login successful",
                "data": {
                    "access": access_token,
                    "refresh": refresh_token,
                }
            })
        else:
            # If the user does not exist, create a new user
            username = email.split(
                "@")[0] if "@" in email else f"user_{os.urandom(4).hex()}"
            first_name = name.split(" ")[0]
            last_name = " ".join(name.split(" ")[1:])

            # Ensure the username is unique, and if not, append a random 4-digit number
            while User.objects.filter(username=username).exists():
                username = f"{username}{random.randint(1000, 9999)}"

            user = User.objects.create_user(
                username=username, email=email, first_name=first_name, last_name=last_name, password=os.urandom(24).hex())

            # Make sure to set the 'is_active' field to True
            user.is_active = True
            user.role = 'user'

            try:
                # Save the user with transaction to ensure consistency
                with transaction.atomic():
                    user.save()

                # Debugging: Print the user status after saving
                print(
                    f"User {user.username} is_active set to {user.is_active}")

            except Exception as e:
                # Catch any potential error during save
                return Response({"error": f"Error saving user: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Generate JWT tokens for the new user with custom claims
            refresh = CustomRefreshToken.for_user(
                user)
            refresh_token = str(refresh)
            access_token = str(refresh.access_token)

            return Response({
                "success": True,
                "statusCode": status.HTTP_200_OK,
                "message": "User created and logged in successfully",
                "data": {
                    "user": {
                        "username": user.username,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "role": user.role,
                    },
                    "access": access_token,
                    "refresh": refresh_token,
                }
            })


class DocumentUploadView(generics.ListCreateAPIView):
    serializer_class = DocumentVerificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DocumentVerification.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            user = request.user
            data ={
                 'is_complete': user.is_profile_complete(),
                 'document': serializer.data
            }
            return success_response("Document uploaded successfully", data)
        return failure_response("Document upload failed", serializer.errors)


class AdminDocumentVerificationView(generics.ListAPIView):
    serializer_class = DocumentVerificationSerializer
    pagination_class = None
    permission_classes = [permissions.IsAdminUser]
    queryset = DocumentVerification.objects.all()

    def list(self, request, *args, **kwargs):
        documents = self.get_queryset()
        serializer = self.get_serializer(documents, many=True)
        return success_response("Document list retrieved successfully", serializer.data)


class ApprovedDocument(generics.UpdateAPIView):
    serializer_class = DocumentVerificationSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = DocumentVerification.objects.all()
    lookup_field = 'id'

    def update(self, request, *args, **kwargs):
        document = self.get_object()
        document.is_verified = True
        user = document.user
        user.is_verified = True
        document.save()
        return success_response("Document approved successfully", None, status.HTTP_200_OK)
