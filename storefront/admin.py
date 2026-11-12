from unfold.admin import ModelAdmin

from django.contrib import admin

from storefront.models import OwnerStorefront, StorefrontProduct


class StorefrontProductInline(admin.TabularInline):
    model = StorefrontProduct
    extra = 0


@admin.register(OwnerStorefront)
class OwnerStorefrontAdmin(ModelAdmin):
    list_display = ('business_name', 'slug', 'owner', 'is_published')
    search_fields = ('business_name', 'slug', 'owner__username')
    inlines = [StorefrontProductInline]


@admin.register(StorefrontProduct)
class StorefrontProductAdmin(ModelAdmin):
    list_display = ('name', 'storefront', 'price', 'is_active')
