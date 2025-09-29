from django.db import models

from django.contrib.auth import get_user_model
User = get_user_model()

class TravelerService(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='traveler_services', null=True, blank=True) 
    from_address = models.CharField(max_length=255)
    to_address = models.CharField(max_length=255)
    from_date_time = models.DateTimeField()
    to_date_time = models.DateTimeField()
    available_space = models.IntegerField()
    price_per_kg= models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ReviewTraveler(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews', null=True, blank=True)
    traveler = models.ForeignKey(TravelerService, on_delete=models.CASCADE)
    rating = models.IntegerField()
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)