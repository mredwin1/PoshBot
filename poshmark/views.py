import datetime
import pytz

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.templatetags.static import static
from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.views import View
from django.views.generic.list import ListView

from .models import PoshUser, Log, LogEntry, Listing, Campaign
from .forms import CreatePoshUser, CreateListing, CreateCampaign, CreateBasicCampaignForm, EditCampaignForm
from .tasks import basic_sharing, advanced_sharing
from poshmark.templatetags.custom_filters import log_entry_return


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


class EditCampaign(View, LoginRequiredMixin):
    form_class = EditCampaignForm

    def get(self, request, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)

        form = self.form_class(request, campaign)

        return render(request, 'poshmark/create_campaign.html', {'form': form})

    def post(self, request, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)

        form = self.form_class(request, campaign, data=request.POST)

        if form.is_valid():
            if form.has_changed():
                form.save()

            return redirect('view-campaigns')
        else:
            return render(request, 'poshmark/create_campaign.html', {'form': form})


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

        logs = logs.order_by('logger_type')

        organized_logs = {}

        for log in logs:
            current_logger_type = log.logger_type
            username = log.posh_user.username
            if current_logger_type in organized_logs.keys():
                if username in organized_logs[current_logger_type].keys():
                    organized_logs[current_logger_type][username].append(log)
                else:
                    organized_logs[current_logger_type][username] = [log]
            else:
                organized_logs[current_logger_type] = {username: [log]}

        return organized_logs


class LogEntryListView(ListView, LoginRequiredMixin):
    model = LogEntry

    def get_queryset(self):
        log_entries = LogEntry.objects.filter(logger=self.kwargs['logger_id']).order_by('timestamp')

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
        posh_users = PoshUser.objects.filter(username__icontains=search, status=PoshUser.ACTIVE).order_by('date_added')

        user_names = [f'{posh_user.username}|{posh_user.id}' for posh_user in posh_users]

        return JsonResponse(user_names, status=200, safe=False)


class SearchListings(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        search = self.request.GET.get('q')
        listings = Listing.objects.filter(title__icontains=search, campaign__isnull=True)

        all_listings = [f'{listing.title}|{listing.id}' for listing in listings]

        return JsonResponse(all_listings, status=200, safe=False)


class GetListingInformation(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        listing_ids = self.request.GET.get('listing_ids', '').split(',')
        data = {}
        if listing_ids:
            for listing_id in listing_ids:
                listing_info = []
                listing = Listing.objects.get(id=int(listing_id))

                listing_info.append(static('poshmark/images/listing.jpg'))
                listing_info.append(listing.title)
                listing_info.append(listing.listing_price)
                listing_info.append(listing.original_price)
                listing_info.append(listing.size)

                data[listing_id] = listing_info

        return JsonResponse(data, status=200, safe=False)


class StopCampaign(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)

        logger = Log.objects.filter(posh_user__username=campaign.posh_user.username).order_by('created').last()
        logger.warning('Stop signal received')

        campaign.status = '3'
        campaign.save()

        return JsonResponse(data={'stopped': 'true'}, status=200, safe=False)


class StartCampaign(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)
        task = None
        task_id = None

        if campaign.mode == Campaign.BASIC_SHARING:
            task = basic_sharing.delay(campaign_id)
        elif campaign.mode == Campaign.ADVANCED_SHARING:
            task = advanced_sharing.delay(campaign_id)

        if task:
            task_id = task.task_id
            campaign.task_id = task.task_id

            campaign.save()

        return JsonResponse(data={'task_id': task_id}, status=200, safe=False)


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


class CreateBasicCampaign(View, LoginRequiredMixin):
    form_class = CreateBasicCampaignForm

    def post(self, request, *args, **kwargs):
        form = self.form_class(request, data=request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({}, status=200)
        else:
            return JsonResponse(form.errors, status=400)
