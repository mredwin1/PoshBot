from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


class CustomUserAdmin(UserAdmin):
    model = User
    list_display = ('username',)
    list_filter = [
        ('is_active', admin.BooleanFieldListFilter),
        ('is_staff', admin.BooleanFieldListFilter)
    ]
    search_fields = ['username']
    fieldsets = (
        ('General Information', {
            'fields': (
                ('is_active', 'is_superuser', 'is_staff'),
                ('username', 'accounts_to_maintain'),
                ('master_email', 'email_password',),
            )
        }),
        ('Groups and Permissions', {
            'classes': ('collapse',),
            'fields': (
                'groups',
                'user_permissions'
            )
        }),
    )


admin.site.register(User, CustomUserAdmin)
