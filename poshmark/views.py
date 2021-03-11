import datetime
import pytz

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.views import View
from django.views.generic.list import ListView

from .models import PoshUser, Log, LogEntry, Listing, Campaign
from .forms import CreatePoshUser, CreateListing, CreateCampaign
from .tasks import basic_campaign
from poshmark.templatetags.custom_filters import log_entry_return
from PoshBot.celery import app


@login_required
def home(request):
    return render(request, 'poshmark/home.html')


@login_required
def create_posh_user(request):
    if request.method == 'GET':
        form = CreatePoshUser(request)

        return render(request, 'poshmark/create_posh_user.html', {'form': form})
    else:
        form = CreatePoshUser(data=request.POST, files=request.FILES, request=request)
        if form.is_valid():
            form.save()

            return redirect('posh-users')
        else:
            return render(request, 'poshmark/create_posh_user.html', {'form': form})


@login_required
def create_listing(request):
    if request.method == 'GET':
        form = CreateListing(request)

        return render(request, 'poshmark/create_listing.html', {'form': form})
    else:
        form = CreateListing(data=request.POST, files=request.FILES, request=request)

        if form.is_valid():
            form.save()

            return redirect('view-listings')
        else:
            return render(request, 'poshmark/create_listing.html', {'form': form})


@login_required
def create_campaign(request):
    if request.method == 'GET':
        form = CreateCampaign(request)

        return render(request, 'poshmark/create_campaign.html', {'form': form})
    else:
        form = CreateCampaign(data=request.POST, files=request.FILES, request=request)
        if form.is_valid():
            form.save()

            return redirect('view-campaigns')
        else:
            return render(request, 'poshmark/create_campaign.html', {'form': form})


@login_required
def delete_posh_user(request, posh_user_id):
    posh_user = PoshUser.objects.get(id=posh_user_id)
    posh_user.delete()

    return redirect('posh-users')


class PoshUserListView(ListView, LoginRequiredMixin):
    model = PoshUser

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            posh_users = PoshUser.objects.all()
        else:
            posh_users = PoshUser.objects.filter(user=self.request.user)

        return posh_users


class ListingListView(ListView, LoginRequiredMixin):
    model = Listing

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            listings = Listing.objects.all()
        else:
            listings = Listing.objects.filter(user=self.request.user)

        organized_listings = []
        limited_list = []
        index = 1
        count = 1
        if len(listings) > 4:
            for listing in listings:
                limited_list.append(listing)
                if count == 4 or index == len(listings):
                    organized_listings.append(limited_list)
                    limited_list = []
                    count = 0
                count += 1
                index += 1
        else:
            for listing in listings:
                limited_list.append(listing)
            organized_listings.append(limited_list)

        return organized_listings


class GeneratePoshUserInfo(View, LoginRequiredMixin):
    @staticmethod
    def get(request, *args, **kwargs):
        new_user = PoshUser()
        data = new_user.generate_sign_up_info()

        return JsonResponse(data=data, status=200)


class ActionLogListView(ListView, LoginRequiredMixin):
    model = Log

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            logs = Log.objects.all()
        else:
            logs = Log.objects.filter(user=self.request.user)

        return logs


class LogEntryListView(ListView, LoginRequiredMixin):
    model = LogEntry

    def get_queryset(self):
        log_entries = LogEntry.objects.filter(logger=self.kwargs['logger_id'])

        return log_entries


class GetLogEntries(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        timestamp_str = self.kwargs['datetime']
        logger_id = self.kwargs["logger_id"]
        timestamp = datetime.datetime.strptime(timestamp_str, '%Y-%m-%d %I:%M:%S.%f %p').replace(tzinfo=pytz.utc)
        log_entries = LogEntry.objects.filter(logger=logger_id, timestamp__gt=timestamp).order_by("timestamp")

        if log_entries:
            log_entry_messages = [log_entry_return(log_entry) for log_entry in log_entries]
            last_timestamp = log_entries.last().timestamp.strftime('%Y-%m-%d %I:%M:%S.%f %p')
            data = {
                'log_entry_messages': log_entry_messages,
                'new_url': reverse('get-log-entries', args=[logger_id, last_timestamp])
            }
        else:
            data = {}

        return JsonResponse(data=data, status=200)


class SearchUserNames(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        search = self.request.GET.get('q')
        posh_users = PoshUser.objects.filter(username__icontains=search)

        user_names = [f'{posh_user.username} | {posh_user.id}' for posh_user in posh_users]

        return JsonResponse(user_names, status=200, safe=False)


class SearchListings(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        search = self.request.GET.get('q')
        listings = Listing.objects.filter(title__icontains=search)

        all_listings = [f'{listing.title} | {listing.id}' for listing in listings]

        return JsonResponse(all_listings, status=200, safe=False)


class StopCampaign(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)

        test = app.control.revoke(campaign.task_id, terminate=True)

        return JsonResponse(data={'revoked': test}, status=200, safe=False)


class StartCampaign(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']

        task = basic_campaign.delay(campaign_id)

        campaign = Campaign.objects.get(id=campaign_id)
        campaign.task_id = task.task_id

        campaign.save()

        return JsonResponse(data={'task_id': task.task_id}, status=200, safe=False)


class CampaignListView(ListView, LoginRequiredMixin):
    model = Campaign

    def get_queryset(self):
        if self.request.user.is_superuser or self.request.user.is_staff:
            campaigns = Campaign.objects.all()
        else:
            campaigns = Campaign.objects.filter(user=self.request.user)

        organized_campaigns = []
        limited_list = []
        index = 1
        count = 1
        if len(campaigns) > 4:
            for campaign in campaigns:
                limited_list.append(campaign)
                if count == 4 or index == len(campaigns):
                    organized_campaigns.append(limited_list)
                    limited_list = []
                    count = 0
                count += 1
                index += 1
        else:
            for campaign in campaigns:
                limited_list.append(campaign)
            organized_campaigns.append(limited_list)
        
        return organized_campaigns
