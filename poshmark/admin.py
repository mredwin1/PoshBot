from django.contrib import admin

from .models import PoshUser, Log, Listing, Campaign, PoshProxy, ProxyConnection


class PoshUserAdmin(admin.ModelAdmin):
    model = PoshUser
    list_display = ('username', 'first_name', 'last_name')
    list_filter = [
        ('status', admin.ChoicesFieldListFilter),
        ('user', admin.RelatedFieldListFilter),
    ]
    search_fields = ['username']
    fieldsets = (
        ('General Information', {
            'fields': (
                ('is_registered', 'profile_updated', ),
                ('profile_picture', 'header_picture'),
                ('first_name', 'last_name'),
                ('username', 'password'),
                ('email', 'email_id', 'profile_picture_id'),
                ('user', 'status', 'gender'),
            )
        }),
    )


admin.site.register(PoshUser, PoshUserAdmin)
admin.site.register(Log)
admin.site.register(Listing)
admin.site.register(Campaign)
admin.site.register(PoshProxy)
admin.site.register(ProxyConnection)
