import datetime
import pytz

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect, reverse
from django.views import View
from django.views.generic.list import ListView

from .models import PoshUser, Log, LogEntry
from .forms import CreatePoshUser
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
