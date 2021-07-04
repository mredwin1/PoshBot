import datetime
import pytz

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.views import View
from django.views.generic.edit import DeleteView
from django.views.generic.list import ListView

from .models import PoshUser, Log, LogEntry, Listing, Campaign, User
from .forms import CreatePoshUser, CreateListing, CreateCampaign, CreateBasicCampaignForm, EditCampaignForm,\
    EditListingForm
from .tasks import basic_sharing, start_campaign
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
        form = CreateListing(request, initial={'lowest_price': 250})

        return render(request, 'poshmark/listings.html', {'form': form})
    else:
        form = CreateListing(data=request.POST, files=request.FILES, request=request)

        if form.is_valid():
            form.save()

            return redirect('view-listings')
        else:
            return render(request, 'poshmark/listings.html', {'form': form})


@login_required
def create_campaign(request):
    if request.method == 'GET':
        form = CreateCampaign(request, initial={'times': '04 AM,05 AM,06 AM,08 AM,07 AM,09 AM,03 PM,01 PM,02 PM,12 PM,11 AM,10 AM,04 PM,05 PM,06 PM,07 PM,08 PM,09 PM,03 AM,02 AM,01 AM,12 AM,11 PM,10 PM'})

        return render(request, 'poshmark/campaigns.html', {'form': form})
    else:
        form = CreateCampaign(data=request.POST, files=request.FILES, request=request)
        if form.is_valid():
            form.save()

            return redirect('view-campaigns')
        else:
            return render(request, 'poshmark/campaigns.html', {'form': form})


class DeletePoshUser(DeleteView):
    model = PoshUser
    success_url = reverse_lazy('posh-users')


class DeleteListing(DeleteView):
    model = Listing
    success_url = reverse_lazy('view-listings')


class DeleteCampaign(DeleteView):
    model = Campaign
    success_url = reverse_lazy('view-campaigns')


class EditCampaign(View, LoginRequiredMixin):
    form_class = EditCampaignForm

    def get(self, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)

        form = self.form_class(request=self.request, campaign=campaign)

        data = {
            'form': form,
            'campaign': campaign
        }

        return render(self.request, 'poshmark/campaigns.html', data)

    def post(self, *args, **kwargs):
        campaign_id = self.kwargs['campaign_id']
        campaign = Campaign.objects.get(id=campaign_id)

        form = self.form_class(request=self.request, campaign=campaign, data=self.request.POST)

        if form.is_valid():
            if form.has_changed():
                form.save()

            return redirect('view-campaigns')
        else:
            data = {
                'form': form,
                'campaign': campaign
            }

            return render(self.request, 'poshmark/campaigns.html', data)


class EditListing(View, LoginRequiredMixin):
    form_class = EditListingForm

    def get(self, *args, **kwargs):
        listing_id = self.kwargs['listing_id']
        listing = Listing.objects.get(id=listing_id)

        form = self.form_class(self.request, listing)

        data = {
            'form': form,
            'listing': listing
        }

        return render(self.request, 'poshmark/listings.html', data)

    def post(self, *args, **kwargs):
        listing_id = self.kwargs['listing_id']
        listing = Listing.objects.get(id=listing_id)

        form = self.form_class(self.request, listing, data=self.request.POST)

        if form.is_valid():
            if form.has_changed():
                form.save()

            return redirect('view-listings')
        else:
            data = {
                'form': form,
                'listing': listing
            }

            return render(self.request, 'poshmark/listings.html', data)


class PoshUserListView(ListView, LoginRequiredMixin):
    model = PoshUser

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(PoshUserListView, self).get_context_data(**kwargs)
        context['usernames'] = [user.username for user in User.objects.exclude(id=self.request.user.id)]

        return context

    def get_queryset(self):
        username = self.request.GET.get('username', '')
        username_select = self.request.GET.get('username_select', '')

        if username_select:
            posh_users = PoshUser.objects.filter(user__username=username_select)
        else:
            posh_users = PoshUser.objects.filter(user=self.request.user)

        if username:
            posh_users = posh_users.filter(username__icontains=username)

        if username_select:
            posh_users = posh_users.filter(user__username=username_select)

        return posh_users


class ListingListView(ListView, LoginRequiredMixin):
    model = Listing

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(ListingListView, self).get_context_data(**kwargs)
        context['usernames'] = [user.username for user in User.objects.exclude(id=self.request.user.id)]

        return context

    def get_queryset(self):
        title = self.request.GET.get('title', '')
        username_select = self.request.GET.get('username_select', '')
        if username_select:
            listings = Listing.objects.filter(user__username=username_select)
        else:
            listings = Listing.objects.filter(user=self.request.user)

        if title:
            listings = listings.filter(title__icontains=title)

        if username_select:
            listings = listings.filter(user__username=username_select)

        return listings


class GeneratePoshUserInfo(View, LoginRequiredMixin):
    @staticmethod
    def get(request, *args, **kwargs):
        new_user = PoshUser()
        data = new_user.generate_sign_up_info()

        return JsonResponse(data=data, status=200)


class ActionLogListView(ListView, LoginRequiredMixin):
    model = Log

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(ActionLogListView, self).get_context_data(**kwargs)
        context['usernames'] = [user.username for user in User.objects.exclude(id=self.request.user.id)]

        return context

    def get_queryset(self):
        username = self.request.GET.get('username', '')
        username_select = self.request.GET.get('username_select', '')
        logs = Log.objects.order_by('-created_date')

        if username_select:
            logs = logs.filter(user__username=username_select)
        else:
            logs = logs.filter(user=self.request.user)

        if username:
            logs = logs.filter(posh_user__icontains=username)

        organized_logs = {}

        for log in logs:
            if log.campaign.title not in organized_logs.keys():
                organized_logs[log.campaign.title] = [log]
            else:
                organized_logs[log.campaign.title].append(log)

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
        posh_users = PoshUser.objects.filter(campaign__isnull=True, user=self.request.user, username__icontains=search).order_by('date_added')

        user_names = [f'{posh_user.username}|{posh_user.id}' for posh_user in posh_users]

        return JsonResponse(user_names, status=200, safe=False)


class SearchListings(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        search = self.request.GET.get('q')
        listings = Listing.objects.filter(title__icontains=search, campaign__isnull=True, user=self.request.user)

        all_listings = [f'{listing.title}|{listing.id}' for listing in listings]

        return JsonResponse(all_listings, status=200, safe=False)


class GetListingInformation(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        listing_ids = self.request.GET.get('listing_ids', '').split(',')
        data = {}
        if listing_ids:
            for listing_id in listing_ids:
                if listing_id:
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
        campaign_ids = self.kwargs['campaign_ids'].split(',')
        data = {}
        stopped_campaigns = []
        for campaign_id in campaign_ids:
            campaign = Campaign.objects.get(id=int(campaign_id))
            if campaign.status == '1':
                logger = Log.objects.filter(campaign=campaign).order_by('created_date').last()
                logger.warning('Stop signal received')

                campaign.status = '3'
                campaign.save()
                stopped_campaigns.append(campaign_id)

        if stopped_campaigns:
            data['success'] = ','.join(stopped_campaigns)
        else:
            data['error'] = 'Campaign could no be stopped: Status not "RUNNING"'

        return JsonResponse(data=data, status=200, safe=False)


class StartCampaign(View, LoginRequiredMixin):
    def get(self, *args, **kwargs):
        campaign_ids = self.kwargs['campaign_ids'].split(',')
        data = {}
        if len(campaign_ids) == 1:
            campaign = Campaign.objects.get(id=int(campaign_ids[0]))
            if campaign.posh_user and campaign.status == '2':
                campaign.status = '4'
                campaign.save()
                if campaign.mode == Campaign.BASIC_SHARING:
                    basic_sharing.delay(int(campaign_ids[0]))
                elif campaign.mode == Campaign.ADVANCED_SHARING:
                    listings = Listing.objects.filter(campaign=campaign)
                    if listings:
                        start_campaign.delay(int(campaign_ids[0]))
                    else:
                        data['error'] = 'Campaign could not be started: No Listings'
            else:
                if campaign.posh_user:
                    data['error'] = 'Campaign could not be started: Not IDLE'
                else:
                    data['error'] = 'Campaign could not be started: No Posh User'

            if 'error' not in data.keys():
                campaign.status = '4'
                campaign.save()

                data['success'] = 'success'
        else:
            started_campaigns = []
            for campaign_id in campaign_ids:
                campaign = Campaign.objects.get(id=int(campaign_id))
                if campaign:
                    if campaign.posh_user and campaign.status == '2':
                        campaign.status = '4'
                        campaign.save()
                        if campaign.mode == Campaign.BASIC_SHARING:
                            basic_sharing.delay(int(campaign_id))
                            started_campaigns.append(campaign_id)
                        elif campaign.mode == Campaign.ADVANCED_SHARING:
                            listings = Listing.objects.filter(campaign=campaign)
                            if listings:
                                start_campaign.delay(int(campaign_id))
                                started_campaigns.append(campaign_id)
            if started_campaigns:
                data['success'] = ','.join(started_campaigns)
            else:
                data['error'] = 'No campaigns to start'
        return JsonResponse(data=data, status=200, safe=False)


class CampaignListView(ListView, LoginRequiredMixin):
    model = Campaign

    def get_context_data(self, *, object_list=None, **kwargs):
        title = self.request.GET.get('title', '')
        username_select = self.request.GET.get('username_select', '')
        campaigns = Campaign.objects.filter(status='1')

        if title:
            campaigns = campaigns.filter(title__icontains=title)

        if username_select:
            campaigns = campaigns.filter(user__username=username_select)
        else:
            campaigns = campaigns.filter(user=self.request.user)

        context = super(CampaignListView, self).get_context_data(**kwargs)
        context['usernames'] = [user.username for user in User.objects.exclude(id=self.request.user.id)]
        context['total_running'] = len(campaigns)

        return context

    def get_queryset(self):
        title = self.request.GET.get('title', '')
        username_select = self.request.GET.get('username_select', '')
        campaigns = Campaign.objects.order_by('status')

        if username_select:
            campaigns = campaigns.filter(user__username=username_select)
        else:
            campaigns = campaigns.filter(user=self.request.user)

        if title:
            campaigns = campaigns.filter(title__icontains=title)

        return campaigns


class CreateBasicCampaign(View, LoginRequiredMixin):
    form_class = CreateBasicCampaignForm

    def post(self, request, *args, **kwargs):
        form = self.form_class(request, data=request.POST)
        if form.is_valid():
            form.save()
            return JsonResponse({}, status=200)
        else:
            return JsonResponse(form.errors, status=400)
