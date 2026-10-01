"""Marketing campaign access — collaborators + property ownership."""

from __future__ import annotations

from django.db.models import Q

from accounts.brand_scoping import filter_by_brand
from accounts.privileges import has_privilege, is_admin_user

from .models import CampaignCollaborator, MarketingCampaign, Property, Tenant


def _property_manage_access(user, prop):
    if not user.is_authenticated:
        return False
    if prop.owner_id == user.id or user.is_staff:
        return True
    return prop.shares.filter(user=user).exists()


def user_can_view_campaign(user, campaign):
    if not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    prop = campaign.property
    if _property_manage_access(user, prop):
        return True
    if campaign.collaborators.filter(user=user).exists():
        return True
    if has_privilege(user, 'view_marketing'):
        if Tenant.objects.filter(user=user, property=prop, is_active=True).exists():
            return True
    return False


def user_can_edit_campaign(user, campaign):
    if not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    prop = campaign.property
    if prop.owner_id == user.id or prop.shares.filter(user=user, role='manager').exists():
        return True
    return campaign.collaborators.filter(user=user, accepted=True, can_edit=True).exists()


def user_can_publish_campaign(user, campaign):
    if not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    if campaign.property.owner_id == user.id:
        return True
    return campaign.collaborators.filter(user=user, accepted=True, can_publish=True).exists()


def user_can_delete_campaign(user, campaign):
    if not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    return campaign.property.owner_id == user.id or campaign.created_by_id == user.id


def user_can_create_campaign_for_property(user, prop, brand=None):
    if not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    if brand is not None and prop.brand_id != brand.id:
        return False
    if _property_manage_access(user, prop):
        return has_privilege(user, 'manage_marketing')
    if prop.allow_tenant_marketing and Tenant.objects.filter(
        user=user, property=prop, is_active=True
    ).exists():
        return has_privilege(user, 'create_marketing') or has_privilege(user, 'collaborate_marketing')
    return False


def campaigns_for_user(user, brand):
    if not user.is_authenticated:
        return MarketingCampaign.objects.none()
    if is_admin_user(user):
        return filter_by_brand(MarketingCampaign.objects.all(), brand)
    props = Property.for_user(user, brand=brand)
    tenant_prop_ids = Tenant.objects.filter(
        user=user, is_active=True, property__brand=brand
    ).values_list('property_id', flat=True)
    collab_ids = CampaignCollaborator.objects.filter(
        user=user, campaign__brand=brand
    ).values_list('campaign_id', flat=True)
    return filter_by_brand(
        MarketingCampaign.objects.filter(
            Q(property__in=props)
            | Q(property_id__in=tenant_prop_ids)
            | Q(pk__in=collab_ids)
        ).distinct(),
        brand,
    )


def pending_collaboration_invites(user, brand):
    if not user.is_authenticated:
        return CampaignCollaborator.objects.none()
    return (
        CampaignCollaborator.objects.filter(
            user=user,
            accepted=False,
            campaign__brand=brand,
        )
        .exclude(role='owner')
        .select_related('campaign', 'campaign__property', 'invited_by')
        .order_by('-invited_at')
    )


def pending_collaboration_invites_count(user, brand):
    return pending_collaboration_invites(user, brand).filter(is_read=False).count()


def active_site_promotions(brand, placement=None):
    from django.utils import timezone

    from .models import SitePromotion

    qs = SitePromotion.objects.filter(brand=brand, is_active=True)
    if placement:
        qs = qs.filter(Q(placement=placement) | Q(placement='both'))
    today = timezone.localdate()
    return [
        p for p in qs.order_by('sort_order', '-created_at')
        if p.is_currently_active(today)
    ]


def ensure_owner_collaborator(campaign):
    owner = campaign.property.owner
    defaults = {
        'role': 'owner',
        'can_edit': True,
        'can_publish': True,
        'accepted': True,
    }
    CampaignCollaborator.objects.update_or_create(
        campaign=campaign,
        user=owner,
        defaults=defaults,
    )
