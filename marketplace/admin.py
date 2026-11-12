from unfold.admin import ModelAdmin

from django.contrib import admin

from marketplace.models import MarketplaceListing


@admin.register(MarketplaceListing)
class MarketplaceListingAdmin(ModelAdmin):
    list_display = ('title', 'kind', 'owner', 'city', 'is_published', 'created_at')
    list_filter = ('kind', 'is_published')
    search_fields = ('title', 'description', 'owner__username', 'city')
