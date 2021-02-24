from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic.list import ListView

from .models import PoshUser
from .forms import CreatePoshUser


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


class GeneratePoshUserInfo(View):
    @staticmethod
    def get(request, *args, **kwargs):
        new_user = PoshUser()
        data = new_user.generate_sign_up_info()

        return JsonResponse(data=data, status=200)

