"""Brand-scoped query helpers — data is isolated per active brand."""

from __future__ import annotations

from django.db.models import Q

from .brands import resolve_brand


def get_request_brand(request):
    """Active brand from middleware or resolve."""
    if request is None:
        return resolve_brand(None)
    return getattr(request, 'brand', None) or resolve_brand(request)


def filter_by_brand(qs, brand):
    """Filter any queryset that has a direct brand FK."""
    if brand is None:
        return qs.none()
    model = qs.model
    if hasattr(model, 'brand_id'):
        return qs.filter(brand=brand)
    return qs


def users_for_brand(brand):
    """Users whose profile belongs to this brand."""
    from django.contrib.auth.models import User

    if brand is None:
        return User.objects.none()
    return User.objects.filter(profile__brand=brand)


def properties_for_brand(brand):
    from properties.models import Property

    return filter_by_brand(Property.objects.all(), brand)


def assign_brand(instance, brand):
    """Set brand on a new row if the model has brand FK."""
    if brand is not None and hasattr(instance, 'brand_id') and not instance.brand_id:
        instance.brand = brand


def stamp_brand_from_property(instance):
    """Copy brand from parent property onto child rows."""
    if not getattr(instance, 'property_id', None):
        return
    if not hasattr(instance, 'brand_id'):
        return
    brand_id = getattr(instance.property, 'brand_id', None)
    if brand_id:
        instance.brand_id = brand_id


def property_in_brand(prop, brand):
    """True if property belongs to the active brand."""
    if brand is None or prop is None:
        return False
    return prop.brand_id == brand.id
