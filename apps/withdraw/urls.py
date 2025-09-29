from rest_framework.routers import DefaultRouter
from django.urls import path, include
from . import dashboard as  views
from .views import(  WithdrawalRequestPublicView,CreateStripeAccountView,
                   CreateWithdrawalRequestView,ApproveWithdrawalView,TravelerEarningsOverviewAPI,
                   MyWithdrawalRequestsView
)
router = DefaultRouter()


urlpatterns = [
    path('', include(router.urls)),
    path('list/', WithdrawalRequestPublicView.as_view(), name='withdrawalrequest-public'),
    path('list/<int:pk>/', WithdrawalRequestPublicView.as_view(), name='withdrawalrequest-public-detail'),
    
    #stripe account
    path('create-stripe-account/', CreateStripeAccountView.as_view(), name='create-stripe-account'),
    
    #withdrawal request
    path('create-withdrawal/', CreateWithdrawalRequestView.as_view(), name='create-withdrawal'),
    
    #withdrawal approval
    path('approve-withdrawal/<int:withdrawal_id>/', ApproveWithdrawalView.as_view(), name='approve-withdrawal'),
    
    
    #dashboard ---------------------
    path("overview/", views.overview, name="dashboard-overview"),
    path("earning-overview/", views.earning_overview, name="dashboard-earning-overview"),
    path("today-traveling/", views.today_traveling, name="dashboard-today-traveling"),
    path("today-join/", views.today_join, name="dashboard-today-join"),
    path("top-travelers/", views.top_travelers, name="dashboard-top-travelers"),
    
    
    #my earnings
    path("my-earnings/", TravelerEarningsOverviewAPI.as_view(), name="my-earnings"),
    
    #my withdrawal requests
    path("my-withdrawal-requests/", MyWithdrawalRequestsView.as_view(), name="my-withdrawal-requests"),

]
