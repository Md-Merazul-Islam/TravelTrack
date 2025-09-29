from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    BookingViewSet,
    BookingPublicView,
    StripeBookingCreateView,
    PaypalBookingCreateView,
    ConfirmPaypalBookingView,
    # CreateWithdrawalRequestView,
    # ApproveWithdrawalRequestView,
    StripeRefundView,
    PayPalRefundView,
    TravelerRequestBookingsView,BookingDetails,
    MyBookedList,ApproveSenderRequest,RejectBookingView,
    BookingTrackingCreateView,ApproveDeliveryRequestView,
    CustomerCancelBookingRequestView,AdminCancelApprovalView,
    DeliveryAcceptRequestListView,RetrieveDeliveryRequestView,
    CancelBookingView
)
from .payment_success import payment_success, payment_fail
from .web_book import stripe_webhook, paypal_webhook
from .paypal_confirm import PayPalReturnConfirmView,PayPalCancelView

router = DefaultRouter()
router.register(r'action', BookingViewSet, basename="booking")

urlpatterns = [
    # Booking API (public + protected)
    path("", include(router.urls)),
    path("public/", BookingPublicView.as_view(), name="booking-public"),
    path("public/<int:pk>/", BookingPublicView.as_view(), name="booking-public-detail"),

    # Payment: Stripe
    path("payment/stripe/", StripeBookingCreateView.as_view(), name="stripe-booking-create"),
    path("payment/stripe/refund/<int:booking_id>/", StripeRefundView.as_view(), name="stripe-refund"),
    path("payment/stripe/webhook/", stripe_webhook, name="stripe-webhook"),

    # Payment: PayPal
    path("payment/paypal/", PaypalBookingCreateView.as_view(), name="paypal-booking-create"),
    path("payment/paypal/confirm/", ConfirmPaypalBookingView.as_view(), name="paypal-confirm-booking"),
    path("payment/paypal/refund/<int:booking_id>/", PayPalRefundView.as_view(), name="paypal-refund"),
    path("payment/paypal/webhook/", paypal_webhook, name="paypal-webhook"),

    # PayPal redirect callbacks
    path("checkout/paypal/confirm/", PayPalReturnConfirmView.as_view(), name="paypal-return-confirm"),
    path("checkout/paypal/cancel/", PayPalCancelView.as_view(), name="paypal-cancel"),
    path("checkout/paypal/success/", payment_success, name="paypal-success"),
    path("checkout/paypal/fail/", payment_fail, name="paypal-fail"),

    # Withdrawals
    # path("withdrawals/", CreateWithdrawalRequestView.as_view(), name="create-withdrawal"),
    # path("withdrawals/<int:pk>/approve/", ApproveWithdrawalRequestView.as_view(), name="approve-withdrawal"),
    
    
    # Traveler Request Bookings
    path("traveler-own-bookings/", TravelerRequestBookingsView.as_view(), name="traveler-request-bookings"),
    path("booking-details/<int:pk>/", BookingDetails.as_view(), name="booking-details"),

    # My Bookings
    path("my-bookings/", MyBookedList.as_view(), name="my-bookings"),
    path("my-bookings/<int:booking_id>/cancel/", CancelBookingView.as_view(), name="cancel-booking"),
    
    
    # Approve Sender Request
    path("approve-sender-request/<int:pk>/", ApproveSenderRequest.as_view(), name="approve-sender-request"),
     path("reject/<int:booking_id>/", RejectBookingView.as_view(), name="reject-booking"),
     
     #order tracking 
       path('order/<int:id>/tracking/', BookingTrackingCreateView.as_view(), name='booking-tracking-create'),
     
     #accept booking sender
      path("accept/<int:booking_id>/order/", ApproveDeliveryRequestView.as_view(), name="accept-booking"),
    
    #customer reject 
     path("customer-reject/<int:booking_id>/order/", CustomerCancelBookingRequestView.as_view(), name="customer-reject-booking"),
     
     #admin reject and approve
     path("admin-approve-reject/<int:booking_id>/order/", AdminCancelApprovalView.as_view(), name="admin-reject-booking"),
     
     #all delivery cancel or  accept list
     path("delivery/manage/list/", DeliveryAcceptRequestListView.as_view(), name="delivery-accept-booking"),
     
     #retrieve delivery request
     path("delivery/<int:booking_id>/order/", RetrieveDeliveryRequestView.as_view(), name="retrieve-delivery-booking"),
      
]
