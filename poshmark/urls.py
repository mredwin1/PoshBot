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
    path('add-posh-user/', posh_views.PoshUserCreateView.as_view(template_name='poshmark/create_posh_user.html'),
         name='add-posh-user'),
    path('generate-posh-user-info/', posh_views.GeneratePoshUserInfo.as_view(), name='generate-posh-user-info'),
]
