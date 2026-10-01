"""Unfold global admin context (brand bar, theme hints)."""

from django.conf import settings
from django.urls import reverse

from .brand_scoping import get_request_brand
from .brands import ensure_default_brands
from .models import Brand


def global_callback(request):
    if not getattr(request.user, 'is_staff', False):
        return {}

    ensure_default_brands()
    brand = get_request_brand(request)
    brands = list(Brand.objects.filter(is_active=True).order_by('name'))
    brand_choices = [
        {
            'name': b.name,
            'slug': b.slug,
            'active': brand and b.id == brand.id,
            'switch_url': reverse('admin:admin_brand_switch', args=[b.slug]),
            'primary_color': b.primary_color or '#0f766e',
        }
        for b in brands
    ]
    primary = (brand.primary_color if brand else None) or '#0f766e'
    header_bg = (brand.header_color if brand else None) or '#0f2744'
    header_text = (brand.header_text_color if brand else None) or '#e8eef7'
    css_parts = []
    if primary.startswith('#'):
        css_parts.append(
            f':root {{ --color-primary-600: {primary}; --color-primary-500: {primary}; }}'
        )
    if header_bg.startswith('#'):
        css_parts.append(
            f'#nav-sidebar, #nav-sidebar-inner {{ background-color: {header_bg} !important; '
            f'color: {header_text}; border-color: rgba(255,255,255,0.08) !important; }}'
        )
    css = '\n'.join(css_parts)
    return {
        'admin_active_brand': brand,
        'admin_brand_choices': brand_choices,
        'admin_brand_css': css,
        'admin_staff_console_url': reverse('staff_dashboard'),
    }
