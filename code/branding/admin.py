from django.contrib import admin
from .models import Contact, Branding

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('firstname', 'lastname', 'email', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'email')

@admin.register(Branding)
class BrandingAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
