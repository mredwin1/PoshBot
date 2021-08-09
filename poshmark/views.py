import datetime
import pytz

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.views import View
from django.views.generic.edit import DeleteView
from django.views.generic.list import ListView

from .models import PoshUser, Log, LogEntry, Listing, Campaign, User
from .forms import CreateListing, CreateCampaign, CreateBasicCampaignForm, EditCampaignForm,\
    EditListingForm
from .tasks import generate_posh_users, start_campaign, update_redis_object, assign_posh_users
from poshmark.templatetags.custom_filters import log_entry_return


@login_required
def home(request):
    return render(request, 'poshmark/home.html')


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


class AssignPoshUsers(View, LoginRequiredMixin):
    def post(self, *args, **kwargs):
        assign_posh_users.delay(self.request.user.id)

        return JsonResponse({}, status=200)


class CreatePoshUsers(View, LoginRequiredMixin):
    def post(self, *args, **kwargs):
        generate_posh_users.delay(self.request.POST['email'], self.request.POST['password'], int(self.request.POST['quantity']), self.request.user.id)

        return JsonResponse(data={'success': f'Please wait, Generating {self.request.POST["quantity"]} users'}, status=200)


class DeletePoshUser(DeleteView, LoginRequiredMixin):
    model = PoshUser
    success_url = reverse_lazy('posh-users')


class DeleteListing(DeleteView, LoginRequiredMixin):
    model = Listing
    success_url = reverse_lazy('view-listings')


class DeleteCampaign(DeleteView, LoginRequiredMixin):
    model = Campaign
    success_url = reverse_lazy('view-campaigns')


class EditCampaign(View, LoginRequiredMixin):
    form_class = EditCampaignForm
    login_url = '/login/'

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
    login_url = '/login/'

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
    login_url = '/login/'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(PoshUserListView, self).get_context_data(**kwargs)
        context['usernames'] = [user.username for user in User.objects.exclude(id=self.request.user.id)]

        return context

    def get_queryset(self):
        search = self.request.GET.get('search', '')
        username_select = self.request.GET.get('username_select', '')

        if username_select:
            posh_users = PoshUser.objects.filter(user__username=username_select)
        else:
            posh_users = PoshUser.objects.filter(user=self.request.user)

        if search:
            posh_users = posh_users.filter(Q(username__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search))

        if username_select:
            posh_users = posh_users.filter(user__username=username_select)

        return posh_users


class ListingListView(ListView, LoginRequiredMixin):
    model = Listing
    login_url = '/login/'

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
        data = PoshUser.generate_sign_up_info()[0]

        return JsonResponse(data=data, status=200)


class ActionLogListView(ListView, LoginRequiredMixin):
    model = Log
    login_url = '/login/'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super(ActionLogListView, self).get_context_data(**kwargs)
        context['usernames'] = [user.username for user in User.objects.exclude(id=self.request.user.id)]

        return context

    def get_queryset(self):
        description = self.request.GET.get('description', '')
        username_select = self.request.GET.get('username_select', '')
        logs = Log.objects.order_by('-created_date')

        if username_select:
            logs = logs.filter(user__username=username_select)
        else:
            logs = logs.filter(user=self.request.user)

        if description:
            logs = logs.filter(description__icontains=description)

        all_logs = {
            'Campaign': {},
            'Email Registration': {},
        }

        for log in logs:
            if log.campaign:
                organized_logs = all_logs['Campaign']
                if log.campaign.title not in organized_logs.keys():
                    organized_logs[log.campaign.title] = [log]
                else:
                    organized_logs[log.campaign.title].append(log)
            else:
                organized_logs = all_logs['Email Registration']
                if log.description not in organized_logs.keys():
                    organized_logs[log.description] = [log]
                else:
                    organized_logs[log.description].append(log)

        return all_logs


class LogEntryListView(ListView, LoginRequiredMixin):
    model = LogEntry
    login_url = '/login/'

    def get_queryset(self):
        log_entries = LogEntry.objects.filter(logger=self.kwargs['logger_id']).order_by('timestamp')

        return log_entries


class GetLogEntries(View, LoginRequiredMixin):
    login_url = '/login/'

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
        posh_users = PoshUser.objects.filter(campaign__isnull=True, user=self.request.user, username__icontains=search, status=PoshUser.IDLE).order_by('date_added')

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

                update_redis_object(campaign.redis_id, {'status': '3'})
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
                if campaign.mode == Campaign.BASIC_SHARING:
                    campaign.status = '4'
                    campaign.save()
                    start_campaign.delay(int(campaign_ids[0]), False)
                elif campaign.mode == Campaign.ADVANCED_SHARING or campaign.mode == Campaign.LIST_ITEM:
                    listings = Listing.objects.filter(campaign=campaign)
                    if listings:
                        campaign.status = '4'
                        campaign.save()
                        start_campaign.delay(int(campaign_ids[0]), True)
                    else:
                        data['error'] = 'Campaign could not be started: No Listings'
                elif campaign.mode == Campaign.REGISTER:
                    if not campaign.posh_user.is_registered:
                        campaign.status = '4'
                        campaign.save()
                        start_campaign.delay(int(campaign_ids[0]), True)
                    else:
                        data['error'] = 'Campaign could not be started: Posh User is already registered'
            else:
                if campaign.posh_user:
                    data['error'] = 'Campaign could not be started: Not IDLE'
                else:
                    data['error'] = 'Campaign could not be started: No Posh User'

            if 'error' not in data.keys():
                data['success'] = 'success'
        else:
            started_campaigns = []
            for campaign_id in campaign_ids:
                campaign = Campaign.objects.get(id=int(campaign_id))
                if campaign:
                    if campaign.posh_user and campaign.status == '2':
                        if campaign.mode == Campaign.BASIC_SHARING:
                            campaign.status = '4'
                            campaign.save()
                            start_campaign.delay(int(campaign_id), False)
                            started_campaigns.append(campaign_id)
                        elif campaign.mode == Campaign.ADVANCED_SHARING or campaign.mode == Campaign.LIST_ITEM:
                            listings = Listing.objects.filter(campaign=campaign)
                            if listings:
                                campaign.status = '4'
                                campaign.save()
                                start_campaign.delay(int(campaign_id), True)
                                started_campaigns.append(campaign_id)
                        elif campaign.mode == Campaign.REGISTER:
                            if not campaign.posh_user.is_registered:
                                campaign.status = '4'
                                campaign.save()
                                start_campaign.delay(int(campaign_id), True)
                                started_campaigns.append(campaign_id)
            if started_campaigns:
                data['success'] = ','.join(started_campaigns)
            else:
                data['error'] = 'No campaigns to start'
        return JsonResponse(data=data, status=200, safe=False)


class CampaignListView(ListView, LoginRequiredMixin):
    model = Campaign
    login_url = '/login/'

    def get_context_data(self, *, object_list=None, **kwargs):
        search = self.request.GET.get('search', '')
        username_select = self.request.GET.get('username_select', '')
        campaigns = Campaign.objects.filter(status='1')

        if search:
            campaigns = campaigns.filter(Q(title__icontains=search) | Q(posh_user__username__icontains=search))

        if username_select:
            campaigns = campaigns.filter(user__username=username_select)
        else:
            campaigns = campaigns.filter(user=self.request.user)

        context = super(CampaignListView, self).get_context_data(**kwargs)
        context['usernames'] = [user.username for user in User.objects.exclude(id=self.request.user.id)]
        context['total_running'] = len(campaigns)

        return context

    def get_queryset(self):
        search = self.request.GET.get('search', '')
        username_select = self.request.GET.get('username_select', '')
        campaigns = Campaign.objects.order_by('status')

        if username_select:
            campaigns = campaigns.filter(user__username=username_select)
        else:
            campaigns = campaigns.filter(user=self.request.user)

        if search:
            campaigns = campaigns.filter(Q(title__icontains=search) | Q(posh_user__username__icontains=search))

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
