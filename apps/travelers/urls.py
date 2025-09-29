from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import TravelerViewSet, TravelerPublicView,ReviewTravelerViewSet,MyServicesView,SingleMyServiceView

router = DefaultRouter()
router.register(r'service', TravelerViewSet)
router.register(r'reviews', ReviewTravelerViewSet, basename='reviewtraveler')

urlpatterns = [
    path('', include(router.urls)),
    path('public/services/', TravelerPublicView.as_view(), name='traveler-public'),
    path('public/<int:pk>/', TravelerPublicView.as_view(), name='traveler-public-detail'),
    
    #my services
    path('my-services/', MyServicesView.as_view(), name='my-services'),
    path('my-services/<int:pk>/', SingleMyServiceView.as_view(), name='my-services-detail'),
]
