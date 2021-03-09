from django.contrib import admin

from .models import PoshUser, Log, Listing


class PoshUserAdmin(admin.ModelAdmin):
    model = PoshUser
    list_display = ('username', 'first_name', 'last_name')
    list_filter = [
        ('is_registered', admin.BooleanFieldListFilter),
        ('status', admin.ChoicesFieldListFilter),
        ('user', admin.RelatedFieldListFilter),
    ]
    search_fields = ['username']
    fieldsets = (
        ('General Information', {
            'fields': (
                ('is_registered', 'is_email_verified'),
                ('profile_picture', 'header_picture'),
                ('first_name', 'last_name'),
                ('username', 'password'),
                ('email',),
                ('masked_email', 'alias_email_id'),
                ('user', 'status', 'gender'),
            )
        }),
    )


admin.site.register(PoshUser, PoshUserAdmin)
admin.site.register(Log)
admin.site.register(Listing)
