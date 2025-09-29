from rest_framework import generics
from apps.bookings.models import Booking
import calendar
from datetime import timedelta
from django.db.models import Sum
from django.utils.timezone import now
from rest_framework import status
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.conf import settings
import stripe
from .models import WithdrawalRequest
from .serializers import WithdrawalRequestSerializer, WithdrawalRequestSerializerCreate
from ..core.crud import DynamicModelViewSet
from ..core.pagination import CustomPagination
from ..core.permissions import IsAdminRole
from ..core.publicApi import BasePublicAPIView
from apps.notification.utils import create_notification
stripe.api_key = settings.STRIPE_SECRET_KEY


class WithdrawalRequestPublicView(BasePublicAPIView):
    # permission_classes = [IsAdminRole]
    def __init__(self, *args, **kwargs):
        super().__init__(model=WithdrawalRequest,
                         serializer_class=WithdrawalRequestSerializer, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().order_by('-requested_at')


class MyWithdrawalRequestsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = WithdrawalRequestSerializer
    pagination_class = None

    def get_queryset(self):
        return WithdrawalRequest.objects.filter(user=self.request.user).order_by('-requested_at')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "success": True,
            "statusCode": status.HTTP_200_OK,
            "message": "Withdrawal requests fetched successfully",
            "data": serializer.data
        })


class CreateStripeAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # If already has an account, return it
        if user.stripe_account_id:
            return Response({
                "success": True,
                "message": "Stripe account already exists",
                "account_id": user.stripe_account_id
            })

        # Create new Stripe Express account
        account = stripe.Account.create(
            type="express",
            country="US",  # change if needed
            email=user.email,
            capabilities={
                "transfers": {"requested": True},
            },
            metadata={
                "app_user_id": str(user.id)
            }
        )

        # Save the account ID
        user.stripe_account_id = account.id
        user.save()

        # Generate onboarding link
        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url=f"{settings.FRONTEND_URL}/stripe/refresh",
            return_url=f"{settings.FRONTEND_URL}/stripe/return",
            type="account_onboarding",
        )

        return Response({
            "success": True,
            "message": "Stripe account created",
            "account_link_url": account_link.url,
            "account_id": account.id
        })


class ApproveWithdrawalView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, withdrawal_id):
        from .models import WithdrawalRequest
        admin_user = request.user

        try:
            withdrawal = WithdrawalRequest.objects.get(
                id=withdrawal_id, is_approved=False)
            withdrawal.approve(
                admin_user, method=request.data.get("method", "stripe"))
            return Response({"success": True, "message": "Withdrawal approved", "transaction_id": withdrawal.transaction_id})
        except WithdrawalRequest.DoesNotExist:
            return Response({"success": False, "message": "Withdrawal not found or already approved"}, status=404)
        except Exception as e:
            return Response({"success": False, "message": str(e)}, status=400)


class CreateWithdrawalRequestView(generics.CreateAPIView):
    serializer_class = WithdrawalRequestSerializerCreate
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        withdrawal = serializer.save(user=request.user)

        # Admin notification
        create_notification(withdrawal.user, "Withdrawal Request",
                            f"Your withdrawal request has been created. ID: {withdrawal.id}")

        return Response({
            "success": True,
            "message": "Withdrawal request created",
            "withdrawal_id": withdrawal.id
        }, status=status.HTTP_201_CREATED)


class ApproveWithdrawalView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, withdrawal_id):
        admin_user = request.user

        try:
            withdrawal = WithdrawalRequest.objects.get(
                id=withdrawal_id,
                is_approved=False
            )
            withdrawal.approve(admin_user)

            return Response({
                "success": True,
                "message": "Withdrawal approved",
                "transaction_id": withdrawal.transaction_id
            })

        except WithdrawalRequest.DoesNotExist:
            return Response({
                "success": False,
                "message": "Withdrawal not found or already approved"
            }, status=404)
        except Exception as e:
            return Response({
                "success": False,
                "message": str(e)
            }, status=400)


class TravelerEarningsOverviewAPI(APIView):
    """
    API to return weekly and monthly traveler earnings overview
    """

    def get(self, request, *args, **kwargs):
        traveler = request.user
        period = request.query_params.get(
            "period", "weekly")  # weekly / monthly
        today = now().date()

        data = []

        if period == "weekly":
            # Last 7 days (including today)
            start_date = today - timedelta(days=6)
            qs = Booking.objects.filter(
                travel_service__user=traveler,
                order_status="delivered",
                created_at__date__gte=start_date,
                created_at__date__lte=today,
            ).values("created_at__date").annotate(total=Sum("total_cost"))

            earnings_map = {str(item["created_at__date"])                            : item["total"] for item in qs}

            # Build response day-wise
            for i in range(7):
                day = start_date + timedelta(days=i)
                label = day.strftime("%a")  # Mon, Tue, etc.
                amount = earnings_map.get(str(day), 0) or 0
                data.append({"label": label, "amount": amount})

        elif period == "monthly":
            # Current year, grouped by month
            qs = Booking.objects.filter(
                travel_service__user=traveler,
                order_status="delivered",
                created_at__year=today.year,
            ).values("created_at__month").annotate(total=Sum("total_cost"))

            earnings_map = {item["created_at__month"]                            : item["total"] for item in qs}

            # Build response for all 12 months
            for m in range(1, 13):
                label = calendar.month_abbr[m]  # Jan, Feb, ...
                amount = earnings_map.get(m, 0) or 0
                data.append({"label": label, "amount": amount})

        return Response({
            "success": True,
            "message": "Traveler earnings overview",
            "data": data,
        })
