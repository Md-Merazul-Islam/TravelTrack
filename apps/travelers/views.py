from django.db.models import Q, Case, When, IntegerField, Value, F
from rest_framework import generics
from apps.core.response import success_response, failure_response
from rest_framework.decorators import action
from .models import TravelerService, ReviewTraveler
from .serializers import TravelerServiceSerializer, ReviewTravelerSerializer, MyServicesViewSerializer
from ..core.crud import DynamicModelViewSet
from ..core.pagination import CustomPagination
from ..core.permissions import IsAdminRole, IsAdminOrTraveler
from ..core.publicApi import BasePublicAPIView
from rest_framework import viewsets, permissions


class TravelerViewSet(DynamicModelViewSet):
    queryset = TravelerService.objects.all()
    serializer_class = TravelerServiceSerializer
    pagination_class = CustomPagination
    permission_classes = [IsAdminOrTraveler]

    def __init__(self, *args, **kwargs):
        kwargs['model'] = TravelerService
        kwargs['serializer_class'] = TravelerServiceSerializer
        kwargs['item_name'] = 'Traveler'
        super().__init__(*args, **kwargs)


class TravelerPublicView(BasePublicAPIView):
    def __init__(self, *args, **kwargs):
        super().__init__(model=TravelerService,
                         serializer_class=TravelerServiceSerializer, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.query_params.get('search', '').strip()
        from_loc = self.request.query_params.get('from', '').strip()
        to_loc = self.request.query_params.get('to', '').strip()
        date = self.request.query_params.get('date', '').strip()
        kg = self.request.query_params.get('kg', '').strip()

        # Basic filters
        if from_loc:
            queryset = queryset.filter(from_address__icontains=from_loc)
        if to_loc:
            queryset = queryset.filter(to_address__icontains=to_loc)
        if date:
            queryset = queryset.filter(from_date_time__date=date)
        if kg:
            queryset = queryset.filter(available_space__gte=int(kg))

        if search:
            # Annotate relevance based on matches
            queryset = queryset.annotate(
                relevance=(
                    Case(When(from_address__icontains=search, then=Value(1)), default=Value(0)) +
                    Case(When(to_address__icontains=search, then=Value(1)), default=Value(0)) +
                    Case(When(user__username__icontains=search,
                         then=Value(1)), default=Value(0))
                )
            ).filter(
                Q(from_address__icontains=search) |
                Q(to_address__icontains=search) |
                Q(user__username__icontains=search)
            ).order_by('-relevance', '-created_at')
        else:
            queryset = queryset.order_by('-created_at')

        return queryset


class ReviewTravelerViewSet(viewsets.ModelViewSet):
    queryset = ReviewTraveler.objects.all()
    serializer_class = ReviewTravelerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save(sender=request.user)  # make sure sender is set
            return success_response("Review created successfully", serializer.data)
        # fix typo here
        return failure_response("Invalid data.", serializer.errors)

    @action(detail=False, methods=['get'], url_path='by-traveler/(?P<traveler_id>[^/.]+)')
    def reviews_by_traveler(self, request, traveler_id=None):
        reviews = self.queryset.filter(traveler_id=traveler_id)
        serializer = self.get_serializer(reviews, many=True)
        return success_response("Reviews fetched successfully", serializer.data)


class MyServicesView(generics.ListAPIView):
    serializer_class = MyServicesViewSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return TravelerService.objects.filter(user=self.request.user).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            return success_response("My services list retrieved successfully", serializer.data)
        except Exception as e:
            return failure_response("Failed to retrieve my services list", str(e))

class SingleMyServiceView(generics.RetrieveAPIView):
    serializer_class = MyServicesViewSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = 'pk'

    def get_queryset(self):
        return TravelerService.objects.filter(user=self.request.user)