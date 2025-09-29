from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterAPIView, LoginView, ProtectedView,
    LogoutView, GetNewAccessTokenView, ForgotPasswordView, PasswordChangeView,
    ResetPasswordView, ProfileView, ValidateOTPView, AllUsers,
    CheckEmailOrCreateUser, ResendVerificationEmailAPIView, DetailSingleProfile,
    DocumentUploadView,AdminDocumentVerificationView,ApprovedDocument,ConnectPaypalView,DetailSingleProfileWithBalance
    

)
from .views import RegisterAPIView, VerifyOTPAPIView, ResendOTPAPIView

router = DefaultRouter()
router.register(r'all-users', AllUsers, basename='allusers')


urlpatterns = [
    # for admin
    path('', include(router.urls)),

    # path('register/', RegisterAPIView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('protected-endpoint/', ProtectedView.as_view(), name='protected'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('document-upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('token/refresh/', GetNewAccessTokenView.as_view(), name='token_refresh'),

    # --- password_change
    path('password-change/', PasswordChangeView.as_view(), name='password_change'),
    path('resend-email-link/',
         ResendVerificationEmailAPIView.as_view(), name='resent-email'),

    # --forgot_password
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('validate-otp/', ValidateOTPView.as_view(), name='validate_otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),

    # ---- google auth
    path('google/', CheckEmailOrCreateUser.as_view(), name='google_login'),


    path("register/", RegisterAPIView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPAPIView.as_view(), name="verify-otp"),
    path("resend-otp/", ResendOTPAPIView.as_view(), name="resend-otp"),


    path("profile/<int:id>/", DetailSingleProfile.as_view(), name="detail_profile"),


    path("admin-document-verification/", AdminDocumentVerificationView.as_view(), name="admin-document-verification"),
    
    
    path("approved-document/<int:id>/", ApprovedDocument.as_view(), name="approved-document"),
    
    #connect paypal
    path("connect-paypal/", ConnectPaypalView.as_view(), name="connect-paypal"),
    
    #show my profile with balance
    path("profile-with-balance/", DetailSingleProfileWithBalance.as_view(), name="detail_profile_with_balance"),

]
