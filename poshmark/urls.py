"""PoshBot URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from . import views as posh_views
from django.urls import path

urlpatterns = [
    path('', posh_views.home, name='home'),
    path('posh-users/', posh_views.PoshUserListView.as_view(template_name='poshmark/view_posh_users.html'),
         name='posh-users'),
    path('add-posh-user/', posh_views.create_posh_user, name='add-posh-user'),
    path('delete-posh-user/<int:posh_user_id>/', posh_views.delete_posh_user, name='delete-posh-user'),
    path('generate-posh-user-info/', posh_views.GeneratePoshUserInfo.as_view(), name='generate-posh-user-info'),
    path('view-action-logs/', posh_views.ActionLogListView.as_view(template_name='poshmark/view_action_logs.html'),
         name='view-action-logs'),
    path('view-action-logs/details/<int:logger_id>/',
         posh_views.LogEntryListView.as_view(template_name='poshmark/view_action_log_details.html'),
         name='view-action-log-details'),
    path('get-log-entries/<int:logger_id>/<str:datetime>/', posh_views.GetLogEntries.as_view(), name='get-log-entries'),
    path(
        'view-listings/',
        posh_views.ListingListView.as_view(template_name='poshmark/view_listings.html'),
        name='view-listings'
    ),
    path('add-listing/', posh_views.create_listing, name='add-listing'),
    path('add-campaign/', posh_views.create_campaign, name='add-campaign'),
    path('edit-campaign/<int:campaign_id>', posh_views.EditCampaign.as_view(), name='edit-campaign'),
    path('view-campaigns/', posh_views.CampaignListView.as_view(template_name='poshmark/view_campaigns.html'),
         name='view-campaigns'),
    path('search-user-names/', posh_views.SearchUserNames.as_view(), name='search-user-names'),
    path('search-listings/', posh_views.SearchListings.as_view(), name='search-listings'),
    path('start-campaign/<int:campaign_id>/', posh_views.StartCampaign.as_view(), name='start-campaign'),
    path('stop-campaign/<int:campaign_id>/', posh_views.StopCampaign.as_view(), name='stop-campaign'),
    path('get-listing-info/', posh_views.GetListingInformation.as_view(), name='get-listing-info'),
    path('add-basic-campaign/', posh_views.CreateBasicCampaign.as_view(), name='add-basic-campaign'),
    ]
