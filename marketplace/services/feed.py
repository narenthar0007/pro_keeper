"""Unified marketplace feed: custom listings + public properties (rent/sale)."""

from __future__ import annotations

from django.db.models import Q

from marketplace.models import MarketplaceListing


def _property_kind(prop):
    if prop.listing_type == 'sale':
        return 'property_sale'
    return 'property_rent'


def _property_price_label(prop):
    if prop.listing_type == 'sale' and prop.sale_price:
        return f'₹ {prop.sale_price:,.0f}'
    if prop.monthly_rent:
        return f'₹ {prop.monthly_rent:,.0f} / month'
    return 'Contact for price'


def public_marketplace_feed(brand, *, kind=None, q=''):
    """Return list of dict rows for templates (newest first)."""
    from properties.models import Property

    items = []

    listing_qs = MarketplaceListing.objects.filter(is_published=True).select_related('owner', 'property_link')
    if brand:
        listing_qs = listing_qs.filter(brand=brand)
    if kind and kind in {c[0] for c in MarketplaceListing.KIND_CHOICES}:
        listing_qs = listing_qs.filter(kind=kind)
    elif kind in ('property_rent', 'property_sale'):
        listing_qs = listing_qs.none()
    if q:
        listing_qs = listing_qs.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(city__icontains=q)
        )

    for row in listing_qs[:200]:
        price_text = ''
        if row.price is not None:
            price_text = f'₹ {row.price:,.0f}'
            if row.price_label:
                price_text += f' {row.price_label}'
        elif row.price_label:
            price_text = row.price_label
        if row.kind == MarketplaceListing.KIND_CONSTRUCTION and row.capacity_sqft:
            cap = f'{row.capacity_sqft:,} sqft capacity'
            price_text = f'{price_text} · {cap}' if price_text else cap
        items.append(
            {
                'source': 'listing',
                'pk': row.pk,
                'kind': row.kind,
                'kind_label': row.get_kind_display_short(),
                'title': row.title,
                'subtitle': row.city or (row.owner.username if row.owner_id else ''),
                'price': price_text or '—',
                'detail_url': None,
                'edit_url': None,
                'created_at': row.created_at,
            }
        )

    if kind is None or kind in ('property_rent', 'property_sale', 'all_properties'):
        prop_qs = Property.for_brand(brand).filter(is_listed_publicly=True).select_related('owner')
        prop_qs = prop_qs.exclude(listing_type='sale', sale_status='sold')
        if kind == 'property_rent':
            prop_qs = prop_qs.filter(listing_type='rent')
        elif kind == 'property_sale':
            prop_qs = prop_qs.filter(listing_type='sale')
        if q:
            prop_qs = prop_qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(city__icontains=q)
                | Q(address__icontains=q)
            )
        for prop in prop_qs[:200]:
            pk = prop.pk
            items.append(
                {
                    'source': 'property',
                    'pk': pk,
                    'kind': _property_kind(prop),
                    'kind_label': prop.get_listing_type_display(),
                    'title': prop.title,
                    'subtitle': prop.city or prop.address[:60],
                    'price': _property_price_label(prop),
                    'detail_url': f'/listings/{pk}/',
                    'edit_url': None,
                    'created_at': prop.updated_at or prop.created_at,
                }
            )

    items.sort(key=lambda x: x['created_at'], reverse=True)
    return items[:250]
