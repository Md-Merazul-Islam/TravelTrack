from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Sum, Count
from django.utils.timezone import now
from datetime import timedelta, date
from apps.auths.models import CustomUser
from apps.travelers.models import TravelerService
from apps.bookings.models import Booking
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncYear


# 1️⃣ Overview API
@api_view(["GET"])
def overview(request):
    total_earning = Booking.objects.filter(payment_status="paid").aggregate(
        total=Sum("total_cost")
    )["total"] or 0

    total_users = CustomUser.objects.count()
    active_listings = TravelerService.objects.count()
    completed_deliveries = Booking.objects.filter(order_status="delivered").count()

    return Response({
        "success": True,
        "data": {
            "total_earning": float(total_earning),
            "total_users": total_users,
            "active_listings": active_listings,
            "completed_deliveries": completed_deliveries,
        }
    })


# 2️⃣ Earning Overview API
@api_view(["GET"])
def earning_overview(request):
    period = request.GET.get("period", "monthly")

    queryset = Booking.objects.filter(payment_status="paid")

    if period == "daily":
        earnings = queryset.annotate(day=TruncDay("created_at")).values("day").annotate(
            total=Sum("total_cost")).order_by("day")
        data = [{"day": e["day"].strftime("%Y-%m-%d"), "amount": float(e["total"])} for e in earnings]

    elif period == "weekly":
        earnings = queryset.annotate(week=TruncWeek("created_at")).values("week").annotate(
            total=Sum("total_cost")).order_by("week")
        data = [{"week": e["week"].strftime("%Y-%m-%d"), "amount": float(e["total"])} for e in earnings]

    elif period == "yearly":
        earnings = queryset.annotate(year=TruncYear("created_at")).values("year").annotate(
            total=Sum("total_cost")).order_by("year")
        data = [{"year": e["year"].year, "amount": float(e["total"])} for e in earnings]

    else:  # monthly default
        earnings = queryset.annotate(month=TruncMonth("created_at")).values("month").annotate(
            total=Sum("total_cost")).order_by("month")
        data = [{"month": e["month"].strftime("%b"), "amount": float(e["total"])} for e in earnings]

    return Response({"success": True, "data": data})


# 3️⃣ Today Traveling API
@api_view(["GET"])
def today_traveling(request):
    today = date.today()
    travels = TravelerService.objects.filter(from_date_time__date=today)

    data = [{
        "traveler_name": t.user.username if t.user else None,
        "from": t.from_address,
        "to": t.to_address,
        "id": t.id
    } for t in travels]

    return Response({"success": True, "data": data})


# 4️⃣ Today Join API
@api_view(["GET"])
def today_join(request):
    today = date.today()
    users = CustomUser.objects.filter(date_joined__date=today)

    data = [{
        "id": u.id,
        "name": u.username,
        "photo": u.photo
    } for u in users]

    return Response({
        "success": True,
        "data": {
            "new_travelers": users.count(),
            "users": data
        }
    })


# 5️⃣ Top Traveler Earnings API
@api_view(["GET"])
def top_travelers(request):
    period = request.GET.get("period", "weekly")
    start_date = now()

    if period == "monthly":
        start_date = start_date - timedelta(days=30)
    elif period == "yearly":
        start_date = start_date - timedelta(days=365)
    else:  # weekly default
        start_date = start_date - timedelta(days=7)

    bookings = (
        Booking.objects.filter(payment_status="paid", created_at__gte=start_date)
        .values("travel_service__user__id", "travel_service__user__username", "travel_service__user__photo")
        .annotate(total=Sum("total_cost"))
        .order_by("-total")[:10]
    )

    data = [{
        "id": b["travel_service__user__id"],
        "name": b["travel_service__user__username"],
        "photo": b["travel_service__user__photo"],
        "earning": float(b["total"])
    } for b in bookings]

    return Response({"success": True, "data": data})
