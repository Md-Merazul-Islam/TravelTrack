from django.shortcuts import get_object_or_404
from apps.bookings.models import DeliveryAcceptRequest, BookingTracking
from .models import DeliveryAcceptRequest
from apps.auths.models import CustomUser
from decimal import Decimal
from django.db import transaction
from apps.core.response import success_response, failure_response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
# from .models import WithdrawalRequest
# from .serializers import WithdrawalRequestSerializer
from rest_framework import generics, permissions
import stripe
from django.conf import settings
from rest_framework.views import APIView
import paypalrestsdk
from rest_framework.response import Response
from .models import Booking
from .serializers import (
    BookingSerializer, StripeBookingSerializer,
    PaypalBookingSerializer, BookingDetailsSerializer,
    BookingTrackingSerializer, MyBookingSerializer,
    DeliveryAcceptRequestSerializer
)
from ..core.crud import DynamicModelViewSet
from ..core.pagination import CustomPagination
from ..core.permissions import IsAdminRole
from ..core.publicApi import BasePublicAPIView
from rest_framework import generics, permissions, status
from .payments import send_paypal_payout, send_paypal_refund
from ..notification.utils import create_notification,send_notification

class BookingViewSet(DynamicModelViewSet):
    queryset = Booking.objects.all()
    serializer_class = BookingSerializer
    pagination_class = CustomPagination
    # permission_classes = [IsAdminRole]

    def __init__(self, *args, **kwargs):
        kwargs['model'] = Booking
        kwargs['serializer_class'] = BookingDetailsSerializer
        kwargs['item_name'] = 'Booking'
        super().__init__(*args, **kwargs)


class BookingPublicView(BasePublicAPIView):
    def __init__(self, *args, **kwargs):
        super().__init__(model=Booking, serializer_class=BookingSerializer, *args, **kwargs)


class StripeBookingCreateView(generics.CreateAPIView):
    queryset = Booking.objects.all()
    serializer_class = StripeBookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        booking = serializer.save()

        send_notification(
            user=request.user,
            title="Stripe Booking Created",
            message=f"Your booking #{booking.orderid} has been created and paid successfully."
        )

        return Response({
            "success": True,
            "message": "Booking created and paid with Stripe successfully ",
            "booking_id": booking.id,
            "transaction_id": booking.transaction_id,
            "payment_status": booking.payment_status,
            "order_status": booking.order_status
        }, status=status.HTTP_201_CREATED)


class StripeRefundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = get_object_or_404(
                Booking, id=booking_id, user=request.user, method="stripe"
            )

            if booking.payment_status != "paid":
                return Response({"error": "Only paid bookings can be refunded."}, status=400)

            # Calculate refund amount (full amount including service charge)
            refund_amount = int(booking.total_cost * 100)  # Convert to cents

            refund = stripe.Refund.create(
                payment_intent=booking.transaction_id,
                amount=refund_amount
            )

            booking.payment_status = "refunded"
            booking.save(update_fields=["payment_status"])

            # Restore available space in travel service
            travel_service = booking.travel_service
            travel_service.available_space += booking.package_size
            travel_service.save(update_fields=["available_space"])

            return Response({
                "success": True,
                "refund_id": refund.id,
                "refunded_amount": float(booking.total_cost),
                "breakdown": {
                    "base_amount": float(booking.base_amount),
                    "service_charge": float(booking.service_charge),
                    "total_refunded": float(booking.total_cost)
                },
                "message": f"Full amount refunded including service charge: ${booking.total_cost}"
            }, status=200)

        except Booking.DoesNotExist:
            return Response({"error": "Booking not found."}, status=404)
        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=400)


class PaypalBookingCreateView(generics.CreateAPIView):
    queryset = Booking.objects.all()
    serializer_class = PaypalBookingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        booking_data = serializer.save()

        return Response({
            "success": True,
            "message": "Booking created. Complete payment via PayPal.",
            "booking_id": booking_data.get("booking_id"),
            "payment_id": booking_data.get("payment_id"),
            "approval_url": booking_data.get("approval_url"),
        }, status=status.HTTP_201_CREATED)


class PayPalRefundView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(
                id=booking_id, user=request.user, method="paypal")

            if booking.payment_status != "paid":
                return Response({"error": "Only paid bookings can be refunded."}, status=400)

            paypalrestsdk.configure({
                "mode": settings.PAYPAL_MODE,
                "client_id": settings.PAYPAL_CLIENT_ID,
                "client_secret": settings.PAYPAL_CLIENT_SECRET,
            })

            payment = paypalrestsdk.Payment.find(booking.transaction_id)
            if not payment:
                return Response({"error": "Payment not found on PayPal"}, status=404)

            # Get sale ID
            sale_id = None
            for resource in payment.transactions[0].related_resources:
                if "sale" in resource:
                    sale_id = resource["sale"]["id"]
                    break

            if not sale_id:
                return Response({"error": "Sale transaction not found"}, status=400)

            sale = paypalrestsdk.Sale.find(sale_id)
            refund = sale.refund({
                "amount": {
                    "total": f"{booking.total_cost:.2f}",
                    "currency": "USD"
                }
            })

            if refund.success():
                booking.payment_status = "refunded"
                booking.save(update_fields=["payment_status"])
                return Response({"success": True, "refund": refund.to_dict()}, status=200)
            else:
                return Response({"error": refund.error}, status=400)

        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=404)
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class ConfirmPaypalBookingView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        payment_id = request.data.get('payment_id')
        payer_id = request.data.get('payer_id')

        if not (payment_id and payer_id):
            return Response({"success": False, "message": "Missing payment_id or payer_id."}, status=400)

        # Configure PayPal SDK
        paypalrestsdk.configure({
            "mode": settings.PAYPAL_MODE,  # sandbox or live
            "client_id": settings.PAYPAL_CLIENT_ID,
            "client_secret": settings.PAYPAL_CLIENT_SECRET,
        })

        payment = paypalrestsdk.Payment.find(payment_id)
        if not payment:
            return Response({"success": False, "message": "Payment not found."}, status=404)

        if payment.execute({"payer_id": payer_id}):
            try:
                booking = Booking.objects.get(transaction_id=payment_id)
            except Booking.DoesNotExist:
                return Response({"success": False, "message": "Booking not found."}, status=404)

            if booking.payment_status == "pending":
                booking.payment_status = "paid"
                travel_service = booking.travel_service
                travel_service.available_space -= booking.package_size
                travel_service.save(update_fields=["available_space"])
                booking.save()
                return Response({"success": True, "message": "Payment confirmed successfully."}, status=200)
            else:
                return Response({"success": False, "message": "Payment already confirmed."}, status=400)
        else:
            return Response({"success": False, "message": "Payment execution failed."}, status=400)


# class CreateWithdrawalRequestView(generics.CreateAPIView):
#     serializer_class = WithdrawalRequestSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def get_serializer_context(self):
#         return {'request': self.request}


# class ApproveWithdrawalRequestView(APIView):
#     permission_classes = [permissions.IsAdminUser]

#     def post(self, request, pk, method='stripe'):
#         try:
#             withdrawal = WithdrawalRequest.objects.get(pk=pk)
#             withdrawal.approve(admin_user=request.user, method=method)
#             return Response({'detail': 'Withdrawal approved successfully'})
#         except WithdrawalRequest.DoesNotExist:
#             return Response({'detail': 'Request not found'}, status=status.HTTP_404_NOT_FOUND)
#         except ValueError as e:
#             return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TravelerRequestBookingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Base queryset: only bookings for this traveler's services
        bookings = Booking.objects.filter(
            travel_service__user=user).order_by('-created_at')

        # Filter by order_status query param
        order_status = request.query_params.getlist('order_status')

        if 'active' in order_status:
            # Treat "active" as all bookings NOT completed/final
            final_statuses = ['delivered', 'rejected', 'cancelled', 'returned', 'pending']
            bookings = bookings.exclude(order_status__in=final_statuses)
            # Remove 'active' so it doesn't conflict with other statuses
            order_status.remove('active')

        # Apply other order_status filters if any remain
        if order_status:
            bookings = bookings.filter(order_status__in=order_status)

        # Optional: filter by traveler approval status
        traveler_approved = request.query_params.get('traveler_approved')
        if traveler_approved is not None:
            if traveler_approved.lower() == 'true':
                bookings = bookings.filter(traveler_approved=True)
            elif traveler_approved.lower() == 'false':
                bookings = bookings.filter(traveler_approved=False)

        # Serialize and return
        serializer = MyBookingSerializer(bookings, many=True)
        return Response({
            "success": True,
            "message": "Bookings retrieved successfully",
            "data": serializer.data
        })


class BookingDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        try:
            booking = Booking.objects.get(pk=pk)
            serializer = BookingDetailsSerializer(booking)
            return success_response("Booking details retrieved successfully", serializer.data)
        except Exception as e:
            return failure_response("Failed to retrieve booking details", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


class MyBookedList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Base queryset: only bookings for this traveler's services
        bookings = Booking.objects.filter(
            user=user).order_by('-created_at')

        # Filter by order_status query param
        order_status = request.query_params.getlist('order_status')

        if 'active' in order_status:
            # Treat "active" as all bookings NOT completed/final
            final_statuses = ['delivered', 'rejected', 'cancelled', 'pending', 'returned']
            bookings = bookings.exclude(order_status__in=final_statuses)
            # Remove 'active' so it doesn't conflict with other statuses
            order_status.remove('active')

        # Apply other order_status filters if any remain
        if order_status:
            bookings = bookings.filter(order_status__in=order_status)

        # Optional: filter by traveler approval status
        traveler_approved = request.query_params.get('traveler_approved')
        if traveler_approved is not None:
            if traveler_approved.lower() == 'true':
                bookings = bookings.filter(traveler_approved=True)
            elif traveler_approved.lower() == 'false':
                bookings = bookings.filter(traveler_approved=False)

        serializer = MyBookingSerializer(bookings, many=True)
        return success_response("My All Bookings list as a sender retrieved successfully", serializer.data)


class ApproveSenderRequest(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            booking = Booking.objects.get(pk=pk)
            booking.traveler_approved = True
            booking.save()
            send_notification(
                user=booking.user,
                title="Traveler Request Approved",
                message=f"Your traveler request for booking #{booking.orderid} has been approved."
            )
            return success_response("Traveler request approved successfully")
        except Exception as e:
            return failure_response("Failed to approve traveler request", str(e), status.HTTP_500_INTERNAL_SERVER_ERROR)


class RejectBookingView(APIView):
    def post(self, request, booking_id):
        booking = Booking.objects.filter(id=booking_id).first()
        if not booking:
            return Response({"success": False, "error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

        if booking.payment_status != "paid":
            return Response({"success": False, "error": "Booking is not paid, no refund required"}, status=status.HTTP_400_BAD_REQUEST)
        # Refund logic
        if booking.method == "stripe":
            try:
                stripe.Refund.create(
                    payment_intent=booking.transaction_id,
                )
                booking.payment_status = "refunded"
                booking.save(update_fields=["payment_status"])
                booking.order_status = "rejected"
                booking.save(update_fields=["order_status"])
                
                #send notification
                send_notification(
                    user=booking.user,
                    title="Booking Rejected",
                    message=f"Your booking #{booking.orderid} has been rejected."
                )
                
            except stripe.error.StripeError as e:
                return Response({"success": False, "error": f"Stripe refund failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif booking.method == "paypal":
            if not send_paypal_refund(booking.transaction_id, booking.total_cost):
                return Response({"error": "PayPal refund failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            booking.payment_status = "refunded"
            booking.save(update_fields=["payment_status"])
            booking.order_status = "rejected"
            booking.save(update_fields=["order_status"])

        return Response({"success": True,  "message": "Booking rejected and refund processed"}, status=status.HTTP_200_OK)


class CancelBookingView(APIView):
    def post(self, request, booking_id):
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        reason = request.data.get("reason", "")

        # Check if booking is in pending status
        if booking.order_status != "pending":
            return Response({
                "success": False,
                "error": "Booking can only be cancelled if status is 'pending'"
            }, status=status.HTTP_400_BAD_REQUEST)

        # Refund if already paid
        if booking.payment_status == "paid":
            if booking.method == "stripe":
                try:
                    stripe.Refund.create(payment_intent=booking.transaction_id)
                    booking.payment_status = "refunded"
                except stripe.error.StripeError as e:
                    return Response({
                        "success": False,
                        "error": f"Stripe refund failed: {str(e)}"
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            elif booking.method == "paypal":
                if not send_paypal_refund(booking.transaction_id, booking.total_cost):
                    return Response({
                        "success": False,
                        "error": "PayPal refund failed"
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                booking.payment_status = "refunded"

        # Cancel the order
        booking.order_status = "cancelled"
        booking.cancelled_reason = reason
        booking.save(update_fields=["order_status", "payment_status", "cancelled_reason"])

        # Notify user
        send_notification(
            user=booking.user,
            title="Booking Cancelled",
            message=f"Your booking #{booking.orderid} has been cancelled."
        )

        return Response({
            "success": True,
            "message": "Booking cancelled successfully"
        }, status=status.HTTP_200_OK)

# Add a tracking update

class BookingTrackingCreateView(generics.CreateAPIView):
    serializer_class = BookingTrackingSerializer

    def post(self, request, id):
        booking = Booking.objects.filter(id=id).first()
        if not booking:
            return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

        # Get status from request data
        status_value = request.data.get('status')

        if status_value == 'delivered':
            # Create delivery acceptance request
            delivery_request, created = DeliveryAcceptRequest.objects.get_or_create(
                booking=booking,
                customer=booking.user,
                traveler=request.user,
                defaults={'request_status': 'pending'}
            )

            if not created:
                return Response({"error": "Delivery request already exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            #send notification
            send_notification(
                user=booking.user,
                title="Delivery completion Request",
                message=f"Your delivery #{booking.orderid} is complete please check you delivery if every think ok then accept the request."
            )
            
            return Response({"success": True, "message": "Delivery request created successfully"}, status=status.HTTP_201_CREATED)
        else:
            data = request.data
            try:
                # Create tracking record
                tracking = BookingTracking.objects.create(
                    booking=booking,
                    status=data.get('status'),
                    location=data.get('location'),
                    note=data.get('note', '')
                )

                # Update booking status
                booking.status = data.get('status')
                booking.order_status = data.get('status')
                booking.save()
                

                #send notification
                send_notification(
                    user=booking.user,
                    title="Booking Status Update",
                    message=f"Your booking #{booking.orderid} status has been updated to {data.get('status')}. Current location: {data.get('location')}"
                )

            except ValueError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            return Response({"success": True, "message": "Status updated successfully"}, status=status.HTTP_201_CREATED)


class ApproveDeliveryRequestView(APIView):
    def post(self, request, booking_id):
        admin_email = settings.ADMIN_EMAIL
        if not admin_email:
            return Response({"error": "Admin email is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            delivery_request = DeliveryAcceptRequest.objects.select_related(
                "booking", "traveler", "customer"
            ).get(booking_id=booking_id, customer=request.user, request_status="pending")
        except DeliveryAcceptRequest.DoesNotExist:
            return Response({"error": "No pending delivery request found"}, status=status.HTTP_404_NOT_FOUND)

        booking = delivery_request.booking
        traveler = delivery_request.traveler

        # get first admin and check email
        admin = CustomUser.objects.filter(role="admin").order_by("id").first()
        if not admin or admin.email != admin_email:
            return Response({"error": "Admin not found or email mismatch"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # update booking status
            booking.order_status = "delivered"
            booking.order_completed = True
            booking.save()

            # Create tracking record for delivered status
            # Use receiver_address as the delivery location
            BookingTracking.objects.create(
                booking=booking,
                status="delivered",
                location=booking.receiver_address,
                note="Package delivered and accepted by customer"
            )

            # approve request
            delivery_request.request_status = "approved"
            delivery_request.save()

            # calculate earnings
            traveler_share = booking.base_amount * Decimal("0.90")
            admin_share = booking.total_cost

            # update balances
            traveler.balance += traveler_share
            traveler.save()

            admin.balance += admin_share
            admin.save()
            
            #send notification
            send_notification(
                user=traveler,
                title="Delivery Completed",
                message=f"Your delivery has been successfully completed. You have earned ${traveler_share} from this delivery."
            )

        return Response({
            "success": True,
            "message": "Delivery approved successfully",
            "traveler_earned": traveler_share,
            "admin_earned": admin_share,
        }, status=status.HTTP_200_OK)


class CustomerCancelBookingRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):
        booking = Booking.objects.filter(
            id=booking_id, user=request.user).first()
        if not booking:
            return Response(
                {"success": False, "error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            # fetch existing delivery request (created when booking was made/accepted)
            delivery_request = DeliveryAcceptRequest.objects.get(
                booking=booking)
        except DeliveryAcceptRequest.DoesNotExist:
            return Response(
                {"success": False, "error": "No delivery request found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # If already cancelled, prevent duplicate
        if delivery_request.request_status == "rejected":
            return Response(
                {"success": False, "error": "This booking is already cancelled"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update delivery request with cancel info
        reason = request.data.get("reason", "")
        delivery_request.rejection_reason = reason
        delivery_request.cancelled_by_customer = True
        delivery_request.request_status = "pending"  # waiting for admin decision
        delivery_request.save(update_fields=[
                              "rejection_reason", "cancelled_by_customer", "request_status",
                              ])

        
        
        #send notification to admin
        admins = CustomUser.objects.filter(role="admin")

        for admin in admins:
            send_notification(
                user=admin,
                title="Cancel Booking Request",
                message=f"Booking #{booking.orderid} has been cancelled. Reason: {reason}"
            )

        return Response(
            {
                "success": True,
                "message": "Cancel request submitted. Awaiting admin approval.",
                "request_id": delivery_request.id,
            },
            status=status.HTTP_200_OK,
        )


class AdminCancelApprovalView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, booking_id):
        try:
            delivery_request = DeliveryAcceptRequest.objects.select_related(
                "booking", "traveler", "customer").get(booking_id=booking_id)
        except DeliveryAcceptRequest.DoesNotExist:
            return Response({"success": False, "error": "Cancel request not found"}, status=status.HTTP_404_NOT_FOUND)

        booking = delivery_request.booking
        action = request.data.get("action")  # "approve" or "reject"

        if action == "approve":
            # Customer cancel request approved → cancel booking + refund
            delivery_request.request_status = "approved"
            delivery_request.save(
                update_fields=["request_status", "updated_at"])

            booking.order_status = "cancelled"
            booking.save(update_fields=["order_status"])

            # Refund logic
            success, message = process_refund(booking)
            #send notification
            send_notification(
                user=booking.user,
                title="Booking Cancelled successfully",
                message=f"Your booking #{booking.orderid} has been cancelled. {message}"
            )
            
            if not success:
                return Response({"success": False, "error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({"success": True, "message": f"Cancel request approved. {message}"}, status=status.HTTP_200_OK)

        elif action == "reject":
            # Customer cancel request rejected → order completes, amounts distributed
            admin_email = settings.ADMIN_EMAIL
            admin = CustomUser.objects.filter(
                role="admin").order_by("id").first()
            if not admin or admin.email != admin_email:
                return Response({"error": "Admin not found or email mismatch"}, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                # update booking
                booking.order_status = "delivered"
                booking.order_completed = True
                booking.save(update_fields=["order_status", "order_completed"])

                # approve delivery request
                delivery_request.request_status = "rejected"  # cancel rejected
                delivery_request.save(
                    update_fields=["request_status", "updated_at"])

                # calculate earnings
                traveler_share = booking.base_amount * Decimal("0.90")
                admin_share = booking.total_cost

                # update balances
                delivery_request.traveler.balance += traveler_share
                delivery_request.traveler.save()

                admin.balance += admin_share
                admin.save()
                
                #send notification sender
                send_notification(
                    user=booking.user,
                    title="Booking cancel request declined",
                    message=f"Your booking #{booking.orderid} cancel request declined by admin. Delivery completed successfully."
                )
                
                #send traveler notification
                send_notification(
                    user=delivery_request.traveler,
                    title="Booking delivered successfully",
                    message=f"Your booking #{booking.orderid} has been delivered. Delivery completed successfully."
                )

                # add tracking
                BookingTracking.objects.create(
                    booking=booking,
                    status="delivered",
                    location=booking.receiver_address,
                    note="Cancel request rejected by admin. Delivery completed successfully."
                )

            return Response({
                "success": True,
                "message": "Cancel request rejected. Delivery completed successfully.",
                "traveler_earned": traveler_share,
                "admin_earned": admin_share,
            }, status=status.HTTP_200_OK)

        return Response({"success": False, "error": "Invalid action"}, status=status.HTTP_400_BAD_REQUEST)


def process_refund(booking):
    if booking.method == "stripe":
        try:
            stripe.Refund.create(
                payment_intent=booking.transaction_id,
            )
            return True, "Refund processed successfully"
        except stripe.error.StripeError as e:
            return False, f"Stripe refund failed: {str(e)}"

    elif booking.method == "paypal":
        if not send_paypal_refund(booking.transaction_id, booking.total_cost):
            return False, "PayPal refund failed"
        return True, "Refund processed successfully"

    return False, "Invalid payment method"


class DeliveryAcceptRequestListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        # optional filter: pending, approved, rejected
        status_filter = request.query_params.get("status")
        queryset = DeliveryAcceptRequest.objects.select_related(
            "booking", "customer", "traveler").order_by("-created_at")

        if status_filter:
            queryset = queryset.filter(request_status=status_filter)

        serializer = DeliveryAcceptRequestSerializer(queryset, many=True)
        return Response(
            {"success": True, "count": queryset.count(), "data": serializer.data},
            status=status.HTTP_200_OK
        )


class RetrieveDeliveryRequestView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request, booking_id):
        try:
            delivery_request = DeliveryAcceptRequest.objects.get(
                booking_id=booking_id)
            serializer = DeliveryAcceptRequestSerializer(delivery_request)
            return Response({"success": True, "data": serializer.data}, status=status.HTTP_200_OK)
        except DeliveryAcceptRequest.DoesNotExist:
            return Response({"success": False, "error": "Delivery request not found"}, status=status.HTTP_404_NOT_FOUND)
