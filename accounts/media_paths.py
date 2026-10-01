"""Brand-scoped upload paths: {brand_slug}/{account_id}/{category}/{filename}."""

from __future__ import annotations

import os
import uuid

from django.utils.text import slugify


def _brand_slug(instance) -> str:
    brand = _resolve_brand(instance)
    if brand is not None:
        return slugify(getattr(brand, 'slug', None) or getattr(brand, 'name', None) or 'default')
    return 'default'


def _resolve_brand(instance):
    if instance is None:
        return None
    if instance.__class__.__name__ == 'Brand':
        return instance
    brand_id = getattr(instance, 'brand_id', None)
    if brand_id:
        return instance.brand
    property_id = getattr(instance, 'property_id', None)
    if property_id:
        prop = instance.property
        if getattr(prop, 'brand_id', None):
            return prop.brand
    building_id = getattr(instance, 'building_id', None)
    if building_id:
        building = instance.building
        if getattr(building, 'brand_id', None):
            return building.brand
    tenant_id = getattr(instance, 'tenant_id', None)
    if tenant_id:
        tenant = instance.tenant
        if getattr(tenant, 'brand_id', None):
            return tenant.brand
        if getattr(tenant, 'property_id', None) and getattr(tenant.property, 'brand_id', None):
            return tenant.property.brand
    campaign_id = getattr(instance, 'campaign_id', None)
    if campaign_id:
        campaign = instance.campaign
        if getattr(campaign, 'brand_id', None):
            return campaign.brand
    enquiry_id = getattr(instance, 'enquiry_id', None)
    if enquiry_id:
        enquiry = instance.enquiry
        if getattr(enquiry, 'brand_id', None):
            return enquiry.brand
    user = getattr(instance, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', True):
        profile = getattr(user, 'profile', None)
        if profile is not None and getattr(profile, 'brand_id', None):
            return profile.brand
    return None


def _account_segment(instance) -> str:
    model = instance.__class__.__name__.lower()
    if model == 'propertyimage' and getattr(instance, 'property_id', None):
        return f'property-{instance.property_id}'
    if model == 'document':
        if getattr(instance, 'property_id', None):
            return f'property-{instance.property_id}'
        if getattr(instance, 'tenant_id', None):
            return f'tenant-{instance.tenant_id}'
        if getattr(instance, 'building_id', None):
            return f'building-{instance.building_id}'
        if getattr(instance, 'deal_id', None):
            return f'saledeal-{instance.deal_id}'
    if model == 'meterreading' and getattr(instance, 'property_id', None):
        return f'property-{instance.property_id}'
    if model == 'userprofile' and getattr(instance, 'user_id', None):
        return f'user-{instance.user_id}'
    if instance.pk:
        return f'{model}-{instance.pk}'
    return f'{model}-new'


def _build_path(instance, filename, category, *, use_original_name=False):
    brand_part = _brand_slug(instance)
    account_part = _account_segment(instance)
    ext = os.path.splitext(filename)[1].lower()
    if not ext or len(ext) > 10:
        ext = '.bin'
    if use_original_name:
        stem = slugify(os.path.splitext(filename)[0])[:48] or category
        final_name = f'{stem}{ext}'
    else:
        stem = slugify(os.path.splitext(filename)[0])[:32] or category
        final_name = f'{stem}-{uuid.uuid4().hex[:8]}{ext}'
    return f'{brand_part}/{account_part}/{category}/{final_name}'


def brand_logo_upload(instance, filename):
    return _build_path(instance, filename, 'logo', use_original_name=True)


def brand_icon_upload(instance, filename):
    return _build_path(instance, filename, 'icon', use_original_name=True)


def brand_banner_upload(instance, filename):
    return _build_path(instance, filename, 'banner')


def user_avatar_upload(instance, filename):
    return _build_path(instance, filename, 'avatar')


def building_photo_upload(instance, filename):
    return _build_path(instance, filename, 'photo')


def property_cover_upload(instance, filename):
    return _build_path(instance, filename, 'cover')


def property_gallery_upload(instance, filename):
    return _build_path(instance, filename, 'gallery')


def tenant_photo_upload(instance, filename):
    return _build_path(instance, filename, 'photo')


def tenant_lease_upload(instance, filename):
    return _build_path(instance, filename, 'lease')


def promotion_image_upload(instance, filename):
    return _build_path(instance, filename, 'promotion')


def complaint_photo_upload(instance, filename):
    return _build_path(instance, filename, 'complaint')


def document_file_upload(instance, filename):
    return _build_path(instance, filename, 'document')


def meter_photo_upload(instance, filename):
    return _build_path(instance, filename, 'meter')


def campaign_cover_upload(instance, filename):
    return _build_path(instance, filename, 'campaign')


def enquiry_photo_upload(instance, filename):
    return _build_path(instance, filename, 'enquiry')


def campaign_proof_upload(instance, filename):
    return _build_path(instance, filename, 'proof')
