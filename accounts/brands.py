"""Resolve the active brand for a request (host / preview / default)."""

from __future__ import annotations

SESSION_KEY = 'preview_brand_slug'


def ensure_default_brands():
    from .models import Brand

    propkeep, created = Brand.objects.get_or_create(
        slug='propkeep',
        defaults={
            'name': 'PropKeep',
            'tagline': 'Property Management',
            'footer_text': 'PropKeep — rent, advance, and listings in one place.',
            'hostnames': 'localhost,127.0.0.1,testserver',
            'base_url': 'http://127.0.0.1:8000',
            'is_default': True,
            'is_active': True,
            'primary_color': '#0b5fff',
            'secondary_color': '#111827',
            'button_color': '#0b5fff',
            'button_text_color': '#ffffff',
            'background_color': '#f4f6f8',
            'surface_color': '#ffffff',
            'text_color': '#111827',
            'header_color': '#0f2744',
            'header_text_color': '#e8eef7',
            'header_active_color': '#12b886',
            'footer_bg_color': '#ffffff',
            'footer_text_color': '#6b7280',
            'font_style': 'syne_source',
            'table_format': 'comfortable',
            'border_radius': 'soft',
        },
    )
    if not created and not propkeep.is_default:
        Brand.objects.filter(is_default=True).exclude(pk=propkeep.pk).update(is_default=False)
        propkeep.is_default = True
        propkeep.save(update_fields=['is_default'])

    Brand.objects.get_or_create(
        slug='checkpro-data',
        defaults={
            'name': 'CheckPro Data',
            'tagline': 'Property Intelligence',
            'footer_text': 'CheckPro Data — verify, track, and report property performance.',
            'hostnames': 'checkpro.localhost,checkpro.local',
            'base_url': 'http://checkpro.localhost:8000',
            'is_default': False,
            'is_active': True,
            'primary_color': '#0f766e',
            'secondary_color': '#134e4a',
            'button_color': '#0d9488',
            'button_text_color': '#ffffff',
            'background_color': '#f0fdfa',
            'surface_color': '#ffffff',
            'text_color': '#134e4a',
            'header_color': '#042f2e',
            'header_text_color': '#ccfbf1',
            'header_active_color': '#2dd4bf',
            'footer_bg_color': '#042f2e',
            'footer_text_color': '#99f6e4',
            'font_style': 'inter_system',
            'table_format': 'striped',
            'border_radius': 'sharp',
        },
    )
    return propkeep


def resolve_brand(request=None):
    """Pick brand by preview query/session, then hostname, then default."""
    from .models import Brand

    ensure_default_brands()
    qs = Brand.objects.filter(is_active=True)

    slug = None
    if request is not None:
        slug = request.GET.get('preview_brand') or request.session.get(SESSION_KEY)
        if request.GET.get('preview_brand') and getattr(request, 'session', None) is not None:
            request.session[SESSION_KEY] = request.GET.get('preview_brand')
        if request.GET.get('clear_brand_preview') and getattr(request, 'session', None) is not None:
            request.session.pop(SESSION_KEY, None)
            slug = None

    if slug:
        brand = qs.filter(slug=slug).first()
        if brand:
            return brand

    host = ''
    if request is not None:
        host = (request.get_host() or '').split(':')[0].lower()
    if host:
        for brand in qs:
            hosts = [h.strip().lower() for h in (brand.hostnames or '').split(',') if h.strip()]
            if host in hosts:
                return brand

    brand = qs.filter(is_default=True).first()
    if brand:
        return brand
    return qs.first() or ensure_default_brands()
