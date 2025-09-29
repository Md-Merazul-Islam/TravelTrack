from django.db.models import Avg
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import TravelerService, ReviewTraveler

User = get_user_model()

# --------------------- User Serializer ---------------------
class UserSerializer(serializers.ModelSerializer):
    review_avg = serializers.SerializerMethodField(read_only=True)
    total_reviews = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email',
            'photo', 'username', 'address', 'phone_number', 'about',
            'review_avg', 'total_reviews'
        ]

    def get_review_avg(self, obj):
        avg = ReviewTraveler.objects.filter(traveler__user=obj).aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg, 2) if avg else 0

    def get_total_reviews(self, obj):
        return ReviewTraveler.objects.filter(traveler__user=obj).count()

# ---------------- Traveler Service Serializer ----------------
class TravelerServiceSerializer(serializers.ModelSerializer):
    traveler_details = UserSerializer(read_only=True, source='user')

    class Meta:
        model = TravelerService
        fields = [
            'id', 'user', 'from_address', 'to_address', 'from_date_time', 'to_date_time',
            'available_space', 'price_per_kg', 'description', 'created_at', 'updated_at', 'traveler_details'
        ]

class MyServicesViewSerializer(serializers.ModelSerializer):
    review_avg = serializers.SerializerMethodField(read_only=True)
    total_reviews = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TravelerService
        fields = [
            'id', 'user', 'from_address', 'to_address', 'from_date_time', 'to_date_time',
            'available_space', 'description', 'price_per_kg', 'created_at', 'updated_at',
            'review_avg', 'total_reviews'
        ]

    def get_review_avg(self, obj):
        # obj is TravelerService instance
        avg = ReviewTraveler.objects.filter(traveler=obj).aggregate(avg_rating=Avg('rating'))['avg_rating']
        return round(avg, 2) if avg else 0

    def get_total_reviews(self, obj):
        return ReviewTraveler.objects.filter(traveler=obj).count()
    
# --------------------- Review Serializer --------------------
class ReviewTravelerSerializer(serializers.ModelSerializer):
    sender_details = UserSerializer(read_only=True, source='sender')

    class Meta:
        model = ReviewTraveler
        fields = [
            'id', 'sender', 'traveler', 'rating', 'message',
            'created_at', 'updated_at', 'sender_details'
        ]
