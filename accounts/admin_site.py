"""Extra routes on Django admin (brand switcher)."""

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path, reverse

from .brands import SESSION_KEY, ensure_default_brands
from .models import Brand


def brand_switch_view(request, slug):
    ensure_default_brands()
    brand = Brand.objects.filter(slug=slug, is_active=True).first()
    if brand:
        request.session[SESSION_KEY] = slug
        request.brand = brand
        messages.success(request, f'Admin scope switched to {brand.name}.')
    else:
        messages.error(request, 'Brand not found.')
    target = request.META.get('HTTP_REFERER') or reverse('admin:index')
    return redirect(target)


def brand_clear_view(request):
    request.session.pop(SESSION_KEY, None)
    messages.info(request, 'Brand preview cleared — using host default.')
    target = request.META.get('HTTP_REFERER') or reverse('admin:index')
    return redirect(target)


def patch_admin_site():
    site = admin.site
    if getattr(site, '_propkeep_patched', False):
        return
    original_get_urls = site.get_urls

    def get_urls():
        custom = [
            path(
                'brand-switch/<slug:slug>/',
                site.admin_view(brand_switch_view),
                name='admin_brand_switch',
            ),
            path(
                'brand-clear/',
                site.admin_view(brand_clear_view),
                name='admin_brand_clear',
            ),
        ]
        return custom + original_get_urls()

    site.get_urls = get_urls
    site._propkeep_patched = True
