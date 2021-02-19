from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.generic.list import ListView
from django.views.generic.edit import CreateView

from .models import PoshUser
from .forms import CreatePoshUser


@login_required
def home(request):
    return render(request, 'poshmark/home.html')


class PoshUserListView(ListView):
    model = PoshUser


class PoshUserCreateView(CreateView):
    model = PoshUser
    form_class = CreatePoshUser


class GeneratePoshUserInfo(View):
    @staticmethod
    def get(request, *args, **kwargs):
        new_user = PoshUser()
        data = new_user.generate_sign_up_info()

        return JsonResponse(data=data, status=200)

