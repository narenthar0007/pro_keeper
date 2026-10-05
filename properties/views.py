from calendar import month_name
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db.models import Case, DecimalField, F, Q, Sum, When
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from accounts.privileges import has_privilege, privilege_required
from accounts.brand_scoping import assign_brand, get_request_brand

from .forms import (
    CampaignCollaboratorInviteForm,
    CampaignContentLogForm,
    ComplaintForm,
    ComplaintOwnerForm,
    EnquiryForm,
    ExpenseForm,
    JoinRequestForm,
    MarketingCampaignForm,
    PlannedVacateForm,
    PropertyForm,
    PropertyImageForm,
    PropertyShareForm,
    RentPaymentForm,
    RentReminderForm,
    TenantForm,
    TenantLoginForm,
)
from .marketing_permissions import (
    active_site_promotions,
    campaigns_for_user,
    ensure_owner_collaborator,
    pending_collaboration_invites,
    user_can_create_campaign_for_property,
    user_can_delete_campaign,
    user_can_edit_campaign,
    user_can_publish_campaign,
    user_can_view_campaign,
)
from .lead_utils import log_lead_activity
from .models import (
    Amenity,
    CampaignCollaborator,
    CampaignContentLog,
    CampaignTaskMessage,
    Complaint,
    Enquiry,
    Expense,
    MarketingCampaign,
    Property,
    PropertyImage,
    PropertyShare,
    RentPayment,
    SitePromotion,
    Tenant,
    TenantJoinRequest,
    income_expense_for_month,
    month_start,
    properties_missing_rent_for_month,
)
from .tenant_access import apply_tenant_login_fields, create_login_for_tenant


def _manageable_property(request, pk):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, brand=brand)
    if not prop.user_can_manage(request.user, brand=brand):
        return None
    return prop


def public_listings(request):
    from .models import ensure_default_amenities

    ensure_default_amenities()
    brand = get_request_brand(request)
    properties = (
        Property.for_brand(brand)
        .filter(is_listed_publicly=True)
        .select_related('owner', 'building')
        .prefetch_related('images', 'amenities', 'building__amenities')
    )
    city = request.GET.get('city', '').strip()
    ptype = request.GET.get('type', '').strip()
    q = request.GET.get('q', '').strip()
    listing_type = request.GET.get('listing_type', '').strip()
    min_price = request.GET.get('min_price', '').strip()
    max_price = request.GET.get('max_price', '').strip()
    bedrooms = request.GET.get('bedrooms', '').strip()
    available = request.GET.get('available', '').strip()
    sort = request.GET.get('sort', '').strip()
    amenity = request.GET.get('amenity', '').strip()

    if city:
        properties = properties.filter(city__icontains=city)
    if ptype:
        properties = properties.filter(property_type=ptype)
    if listing_type in ('rent', 'sale'):
        properties = properties.filter(listing_type=listing_type)
    if q:
        properties = properties.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(address__icontains=q)
            | Q(landmark__icontains=q)
        )
    if min_price:
        if listing_type == 'sale':
            properties = properties.filter(sale_price__gte=min_price)
        elif listing_type == 'rent':
            properties = properties.filter(monthly_rent__gte=min_price)
        else:
            properties = properties.filter(
                Q(monthly_rent__gte=min_price) | Q(sale_price__gte=min_price)
            )
    if max_price:
        if listing_type == 'sale':
            properties = properties.filter(sale_price__lte=max_price)
        elif listing_type == 'rent':
            properties = properties.filter(monthly_rent__lte=max_price)
        else:
            properties = properties.filter(
                Q(monthly_rent__lte=max_price) | Q(sale_price__lte=max_price)
            )
    if bedrooms:
        properties = properties.filter(bedrooms__gte=bedrooms)
    if amenity:
        properties = properties.filter(
            Q(amenities__code=amenity) | Q(building__amenities__code=amenity)
        ).distinct()
    if available == '1':
        properties = properties.filter(
            Q(listing_type='rent', is_occupied=False)
            | Q(listing_type='sale', sale_status='available')
        )
    properties = properties.exclude(listing_type='sale', sale_status='sold')

    properties = properties.annotate(
        sort_price=Case(
            When(listing_type='sale', then=F('sale_price')),
            default=F('monthly_rent'),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )
    if sort == 'price_asc':
        properties = properties.order_by('sort_price')
    elif sort == 'price_desc':
        properties = properties.order_by('-sort_price')
    elif sort == 'newest':
        properties = properties.order_by('-created_at')

    from django.urls import reverse

    from accounts.ui_components import (
        build_button,
        build_empty,
        build_filter,
        build_listing,
        build_listings,
    )

    listings_filter = build_filter(
        [
            {
                'name': 'q',
                'label': 'Search',
                'type': 'search',
                'value': q,
                'placeholder': 'Area, landmark, title...',
                'span': '2',
            },
            {'name': 'city', 'label': 'City', 'value': city, 'placeholder': 'Chennai'},
            {
                'name': 'type',
                'label': 'Type',
                'type': 'select',
                'value': ptype,
                'choices': [('', 'All types')] + list(Property.PROPERTY_TYPES),
            },
            {
                'name': 'listing_type',
                'label': 'Listing',
                'type': 'select',
                'value': listing_type,
                'choices': [
                    ('', 'All'),
                    ('rent', 'For rent'),
                    ('sale', 'For sale'),
                ],
            },
            {
                'name': 'min_price',
                'label': 'Min price',
                'type': 'number',
                'value': min_price,
                'placeholder': '0',
            },
            {
                'name': 'max_price',
                'label': 'Max price',
                'type': 'number',
                'value': max_price,
                'placeholder': '5000000',
            },
            {
                'name': 'bedrooms',
                'label': 'Min beds',
                'type': 'number',
                'value': bedrooms,
                'min': '1',
            },
            {
                'name': 'amenity',
                'label': 'Amenity',
                'type': 'select',
                'value': amenity,
                'choices': [('', 'Any')] + [
                    (a.code, a.label)
                    for a in Amenity.objects.exclude(code='others').order_by('label')
                ],
            },
            {
                'name': 'sort',
                'label': 'Sort',
                'type': 'select',
                'value': sort,
                'choices': [
                    ('', 'Default'),
                    ('price_asc', 'Price ↑'),
                    ('price_desc', 'Price ↓'),
                    ('newest', 'Newest'),
                ],
            },
            {
                'name': 'available',
                'label': 'Available only',
                'type': 'checkbox',
                'value': '1',
                'checked': available == '1',
            },
        ],
        submit_label='Search',
        aria_label='Search listings',
    )

    listing_cards = []
    for prop in properties:
        badges = [{'label': prop.get_property_type_display(), 'tone': ''}]
        if prop.is_for_sale:
            badges.append({'label': 'For sale', 'tone': 'sale'})
            badges.append({'label': prop.get_sale_status_display(), 'tone': prop.sale_status})
            lines = [f'Furnishing: {prop.get_furnishing_display()}']
        else:
            badges.append(
                {
                    'label': 'Occupied' if prop.is_occupied else 'Available',
                    'tone': 'occupied' if prop.is_occupied else 'vacant',
                }
            )
            lines = [f'Advance from ₹{prop.advance_amount:,.0f}']
        listing_cards.append(
            build_listing(
                prop.title,
                href=reverse('public_detail', args=[prop.pk]),
                meta=f'{(prop.unit_label + " · ") if prop.building_id else ""}{prop.city} · {prop.bedrooms} bed · {prop.bathrooms} bath',
                price=prop.display_price.replace('/mo', '').strip(),
                price_suffix=' /mo' if prop.is_for_rent else '',
                image_url=prop.get_cover_url(),
                badges=badges,
                lines=lines,
            )
        )

    hero_actions = []
    if not request.user.is_authenticated:
        hero_actions = [
            build_button('List your property', href=reverse('register'), variant='primary'),
            build_button('Owner login', href=reverse('login'), variant='secondary'),
        ]

    return render(
        request,
        'properties/public_listings.html',
        {
            'properties': properties,
            'property_types': Property.PROPERTY_TYPES,
            'selected_city': city,
            'selected_type': ptype,
            'selected_q': q,
            'selected_listing_type': listing_type,
            'selected_min_price': min_price,
            'selected_max_price': max_price,
            'selected_bedrooms': bedrooms,
            'selected_available': available,
            'selected_sort': sort,
            'listings_filter': listings_filter,
            'listing_cards': build_listings(listing_cards),
            'listings_empty': build_empty('No public listings match your filters.'),
            'hero_actions': hero_actions,
        },
    )


def public_property_detail(request, pk):
    brand = get_request_brand(request)
    prop = get_object_or_404(
        Property.objects.select_related('building').prefetch_related(
            'images', 'amenities', 'building__amenities'
        ),
        pk=pk,
        is_listed_publicly=True,
        brand=brand,
    )
    if request.method == 'POST' and request.POST.get('form_name') == 'join_request':
        return _handle_join_request(request, prop)
    if request.method == 'POST':
        form = EnquiryForm(request.POST)
        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.property = prop
            assign_brand(enquiry, brand)
            enquiry.save()
            log_lead_activity(enquiry, verb='created', message='Public enquiry')
            if prop.owner_id:
                from .notifications import notify_user

                notify_user(
                    user=prop.owner,
                    brand=brand,
                    kind='enquiry',
                    title=f'New lead: {enquiry.name} on {prop.title}',
                    url=reverse('lead_detail', args=[enquiry.pk]),
                )
            if prop.owner.email:
                send_mail(
                    subject=f'New enquiry for {prop.title}',
                    message=(
                        f'From: {enquiry.name} <{enquiry.email}>\n'
                        f'Phone: {enquiry.phone}\n\n{enquiry.message}'
                    ),
                    from_email=None,
                    recipient_list=[prop.owner.email],
                    fail_silently=True,
                )
            messages.success(request, 'Enquiry sent. The owner will contact you soon.')
            return redirect('public_detail', pk=prop.pk)
    else:
        form = EnquiryForm()

    is_saved = False
    if request.user.is_authenticated:
        from .models import SavedListing

        is_saved = SavedListing.objects.filter(
            user=request.user, property=prop, brand=brand
        ).exists()
    amenity_labels = list(
        prop.amenities.exclude(code='others').values_list('label', flat=True)
    )
    if prop.building_id:
        amenity_labels = list(
            dict.fromkeys(
                amenity_labels
                + list(prop.building.amenities.values_list('label', flat=True))
            )
        )

    join_ctx = _join_request_context(request, prop)

    return render(
        request,
        'properties/public_detail.html',
        {
            'property': prop,
            'enquiry_form': form,
            'is_saved': is_saved,
            'amenity_labels': amenity_labels,
            **join_ctx,
        },
    )


def _join_request_context(request, prop):
    from accounts.models import UserProfile
    from accounts.privileges import get_user_role

    ctx = {
        'can_request_join': False,
        'join_request_form': JoinRequestForm(),
        'pending_join_request': None,
    }
    user = request.user
    if not user.is_authenticated:
        return ctx
    if not prop.is_for_rent or prop.is_occupied:
        return ctx
    if prop.owner_id == user.id:
        return ctx
    if get_user_role(user) != UserProfile.ROLE_TENANT:
        return ctx
    if prop.tenants.filter(user=user, is_active=True).exists():
        return ctx
    pending = prop.join_requests.filter(user=user, status='pending').first()
    ctx['pending_join_request'] = pending
    ctx['can_request_join'] = pending is None
    return ctx


def _handle_join_request(request, prop):
    from accounts.models import UserProfile
    from accounts.privileges import get_user_role
    from .notifications import notify_user

    brand = get_request_brand(request)
    if not request.user.is_authenticated:
        messages.error(request, 'Log in as a tenant to request this vacant property.')
        return redirect('login')
    if get_user_role(request.user) != UserProfile.ROLE_TENANT:
        messages.error(request, 'Only tenant accounts can request to join a vacant property.')
        return redirect('public_detail', pk=prop.pk)
    if not prop.is_for_rent or prop.is_occupied:
        messages.error(request, 'This property is not vacant.')
        return redirect('public_detail', pk=prop.pk)
    form = JoinRequestForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Could not send the request.')
        return redirect('public_detail', pk=prop.pk)
    if prop.join_requests.filter(user=request.user, status='pending').exists():
        messages.info(request, 'You already requested this property. Wait for the owner to add you.')
        return redirect('public_detail', pk=prop.pk)
    TenantJoinRequest.objects.create(
        property=prop,
        brand=brand,
        user=request.user,
        message=form.cleaned_data.get('message') or '',
    )
    notify_user(
        user=prop.owner,
        brand=brand,
        kind='join_request',
        title=f'{request.user.username} asked to join {prop.title}',
        url=reverse('property_manage', args=[prop.pk]),
    )
    messages.success(request, 'Request sent. The owner needs to add you to this property.')
    return redirect('public_detail', pk=prop.pk)

def marketing(request):
    from django.urls import reverse
    from django.utils.safestring import mark_safe

    from accounts.components import (
        build_button,
        build_empty,
        build_filter,
        build_kpis,
        build_page_header,
        build_search,
        build_table,
    )

    brand = get_request_brand(request)
    pending_invites = pending_collaboration_invites(request.user, brand) if request.user.is_authenticated else []
    if request.user.is_authenticated and not has_privilege(request.user, 'view_marketing'):
        if not pending_invites.exists():
            return HttpResponseForbidden('Not allowed')
    if not request.user.is_authenticated:
        promos = active_site_promotions(brand, placement='marketing_page')
        return render(
            request,
            'properties/marketing.html',
            {
                'promotions': promos,
                'login_required_msg': True,
            },
        )

    q = request.GET.get('q', '').strip()
    channel = request.GET.get('channel', '').strip()
    status = request.GET.get('status', '').strip()
    campaigns = campaigns_for_user(request.user, brand).select_related(
        'property', 'created_by'
    )
    if q:
        campaigns = campaigns.filter(
            Q(title__icontains=q) | Q(property__title__icontains=q)
        )
    if channel:
        campaigns = campaigns.filter(channel=channel)
    if status:
        campaigns = campaigns.filter(status=status)

    promos = active_site_promotions(brand, placement='marketing_page')
    active_count = campaigns.filter(status='active').count()
    total_spend = campaigns.aggregate(total=Sum('spend'))['total'] or Decimal('0')
    total_leads = campaigns.aggregate(total=Sum('leads_count'))['total'] or 0
    unread_invites = sum(1 for invite in pending_invites if not invite.is_read)

    can_create = (
        has_privilege(request.user, 'manage_marketing')
        or has_privilege(request.user, 'create_marketing')
    )
    header_actions = []
    if can_create:
        header_actions.append(
            build_button('New campaign', href=reverse('campaign_create'), variant='primary')
        )

    from django.middleware.csrf import get_token

    csrf = get_token(request)
    invite_rows = []
    for invite in pending_invites:
        campaign = invite.campaign
        inviter = invite.invited_by.username if invite.invited_by_id else '—'
        campaign_url = reverse('campaign_detail', args=[campaign.pk])
        accept_url = reverse('campaign_accept_invite', args=[invite.pk])
        decline_url = reverse('campaign_decline_invite', args=[invite.pk])
        invite_rows.append(
            {
                'when': invite.invited_at.strftime('%d %b %Y %H:%M'),
                'from': inviter,
                'campaign': mark_safe(
                    f'<a href="{campaign_url}">{campaign.title}</a>'
                ),
                'property': campaign.property.title,
                'role': invite.get_role_display(),
                'message': invite.invite_message or '—',
                'actions': mark_safe(
                    f'<form method="post" action="{accept_url}" style="display:inline">'
                    f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">'
                    f'<button class="btn btn-primary btn-sm" type="submit">Accept</button>'
                    f'</form> '
                    f'<form method="post" action="{decline_url}" style="display:inline;margin-left:.35rem">'
                    f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">'
                    f'<button class="btn btn-secondary btn-sm" type="submit">Decline</button>'
                    f'</form>'
                ),
            }
        )
    pending_invites.update(is_read=True)

    rows = []
    for c in campaigns:
        period = '—'
        if c.start_date or c.end_date:
            start = c.start_date.strftime('%d %b %Y') if c.start_date else '…'
            end = c.end_date.strftime('%d %b %Y') if c.end_date else '…'
            period = f'{start} – {end}'
        rows.append(
            {
                'property': c.property.title,
                'campaign': mark_safe(
                    f'<a href="{reverse("campaign_detail", args=[c.pk])}">{c.title}</a>'
                ),
                'channel': c.get_channel_display(),
                'status': c.get_status_display(),
                'budget': f'₹{c.budget:,.0f}' if c.budget else '—',
                'spend': f'₹{c.spend:,.0f}',
                'leads': c.leads_count,
                'period': period,
                'actions': mark_safe(
                    f'<a class="btn btn-secondary btn-sm" href="{reverse("campaign_edit", args=[c.pk])}">Edit</a>'
                ),
            }
        )

    marketing_filter = build_filter(
        [
            build_search(name='q', value=q, placeholder='Campaign or property...', label='Search'),
            {
                'name': 'channel',
                'label': 'Channel',
                'type': 'select',
                'value': channel,
                'choices': [('', 'All channels')] + list(MarketingCampaign.CHANNEL_CHOICES),
            },
            {
                'name': 'status',
                'label': 'Status',
                'type': 'select',
                'value': status,
                'choices': [('', 'All statuses')] + list(MarketingCampaign.STATUS_CHOICES),
            },
        ],
        submit_label='Filter',
        aria_label='Filter campaigns',
    )

    return render(
        request,
        'properties/marketing.html',
        {
            'page_header': build_page_header(
                'Marketing',
                subtitle='Campaigns, channels, and brand promotions.',
                actions=header_actions,
            ),
            'marketing_kpis': build_kpis(
                [
                    {'label': 'Active campaigns', 'value': active_count},
                    {'label': 'Total spend', 'value': f'₹{total_spend:,.0f}'},
                    {'label': 'Total leads', 'value': total_leads},
                    {
                        'label': 'Collaboration requests',
                        'value': len(invite_rows),
                        'tone': 'warn' if unread_invites else 'ok',
                    },
                ]
            ),
            'collaboration_invites_table': build_table(
                id='collaboration-invites',
                columns=[
                    {'key': 'when', 'label': 'When', 'width': '140px'},
                    {'key': 'from', 'label': 'From'},
                    {'key': 'campaign', 'label': 'Campaign', 'html': True},
                    {'key': 'property', 'label': 'Property'},
                    {'key': 'role', 'label': 'Role', 'badge': True},
                    {'key': 'message', 'label': 'Message'},
                    {'key': 'actions', 'label': '', 'width': '180px', 'html': True},
                ],
                rows=invite_rows,
                empty_text='No pending collaboration requests.',
            ),
            'show_collaboration_invites': bool(invite_rows),
            'marketing_filter': marketing_filter,
            'campaigns_table': build_table(
                id='marketing-campaigns',
                columns=[
                    {'key': 'property', 'label': 'Property'},
                    {'key': 'campaign', 'label': 'Campaign', 'html': True},
                    {'key': 'channel', 'label': 'Channel'},
                    {'key': 'status', 'label': 'Status', 'badge': True},
                    {'key': 'budget', 'label': 'Budget'},
                    {'key': 'spend', 'label': 'Spend'},
                    {'key': 'leads', 'label': 'Leads'},
                    {'key': 'period', 'label': 'Period'},
                    {'key': 'actions', 'label': '', 'html': True, 'width': '80px'},
                ],
                rows=rows,
                empty_text='No campaigns yet.',
            ),
            'campaigns_empty': build_empty(
                'No marketing campaigns yet.',
                action_label='Create campaign' if can_create else '',
                action_href=reverse('campaign_create') if can_create else '',
            ),
            'promotions': promos,
        },
    )


@login_required
def campaign_create(request):
    brand = get_request_brand(request)
    if not (
        has_privilege(request.user, 'manage_marketing')
        or has_privilege(request.user, 'create_marketing')
    ):
        return HttpResponseForbidden('Not allowed')
    if request.method == 'POST':
        form = MarketingCampaignForm(request.POST, user=request.user, brand=brand)
        if form.is_valid():
            campaign = form.save(commit=False)
            prop = campaign.property
            if not user_can_create_campaign_for_property(request.user, prop, brand):
                messages.error(request, 'You cannot create a campaign for that property.')
            else:
                campaign.created_by = request.user
                campaign.save()
                ensure_owner_collaborator(campaign)
                messages.success(request, 'Campaign created.')
                return redirect('campaign_detail', pk=campaign.pk)
    else:
        form = MarketingCampaignForm(user=request.user, brand=brand)
    return render(
        request,
        'properties/campaign_form.html',
        {'form': form, 'mode': 'add'},
    )


@login_required
@ensure_csrf_cookie
def campaign_detail(request, pk):
    brand = get_request_brand(request)
    campaign = get_object_or_404(
        MarketingCampaign.objects.select_related('property', 'created_by'),
        pk=pk,
        brand=brand,
    )
    if not user_can_view_campaign(request.user, campaign):
        return HttpResponseForbidden('Not allowed')
    campaign.collaborators.filter(
        user=request.user,
        accepted=False,
        is_read=False,
    ).update(is_read=True)
    collaborators = campaign.collaborators.select_related('user', 'invited_by')
    invite_form = CampaignCollaboratorInviteForm()
    can_invite = user_can_edit_campaign(request.user, campaign)
    can_edit = user_can_edit_campaign(request.user, campaign)
    today = timezone.localdate()
    today_done = campaign.content_done_for_date(today)
    totals = campaign.content_totals()
    my_log = CampaignContentLog.objects.filter(
        campaign=campaign, user=request.user, work_date=today
    ).first()
    content_form = CampaignContentLogForm(
        initial={
            'photos_count': my_log.photos_count if my_log else 0,
            'videos_count': my_log.videos_count if my_log else 0,
            'note': my_log.note if my_log else '',
        }
    )
    can_log_content = (
        can_edit
        or campaign.collaborators.filter(
            user=request.user, accepted=True
        ).exists()
        or campaign.property.owner_id == request.user.id
    )
    recent_logs = campaign.content_logs.select_related('user')[:14]
    my_task_messages = CampaignTaskMessage.objects.filter(
        campaign=campaign,
        recipient=request.user,
    ).order_by('-created_at')[:10]
    from accounts.components import build_kpis

    return render(
        request,
        'properties/campaign_detail.html',
        {
            'campaign': campaign,
            'collaborators': collaborators,
            'invite_form': invite_form,
            'can_invite': can_invite,
            'can_edit': can_edit,
            'can_delete': user_can_delete_campaign(request.user, campaign),
            'content_form': content_form,
            'can_log_content': can_log_content,
            'today': today,
            'today_done': today_done,
            'content_totals': totals,
            'recent_logs': recent_logs,
            'my_task_messages': my_task_messages,
            'photos_required': campaign.total_photos_required(),
            'videos_required': campaign.total_videos_required(),
            'schedule_days': campaign.schedule_days(),
            'kpis': build_kpis(
                [
                    {
                        'label': 'Budget',
                        'value': f'₹{campaign.budget:.0f}' if campaign.budget else '—',
                    },
                    {'label': 'Spend', 'value': f'₹{campaign.spend:.0f}'},
                    {'label': 'Leads', 'value': campaign.leads_count},
                    {'label': 'Photos / day', 'value': campaign.photos_per_day},
                    {'label': 'Videos / day', 'value': campaign.videos_per_day},
                ]
            ),
        },
    )


@login_required
def campaign_edit(request, pk):
    brand = get_request_brand(request)
    campaign = get_object_or_404(MarketingCampaign, pk=pk, brand=brand)
    if not user_can_edit_campaign(request.user, campaign):
        return HttpResponseForbidden('Not allowed')
    if request.method == 'POST':
        form = MarketingCampaignForm(
            request.POST,
            instance=campaign,
            user=request.user,
            brand=brand,
        )
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.status == 'active' and not user_can_publish_campaign(
                request.user, campaign
            ):
                messages.error(request, 'You cannot publish this campaign.')
            else:
                updated.save()
                messages.success(request, 'Campaign updated.')
                return redirect('campaign_detail', pk=campaign.pk)
    else:
        form = MarketingCampaignForm(
            instance=campaign,
            user=request.user,
            brand=brand,
        )
    return render(
        request,
        'properties/campaign_form.html',
        {'form': form, 'mode': 'edit', 'campaign': campaign},
    )


@login_required
@require_POST
def campaign_delete(request, pk):
    brand = get_request_brand(request)
    campaign = get_object_or_404(MarketingCampaign, pk=pk, brand=brand)
    if not user_can_delete_campaign(request.user, campaign):
        return HttpResponseForbidden('Not allowed')
    campaign.delete()
    messages.success(request, 'Campaign deleted.')
    return redirect('marketing')


@login_required
@require_POST
def campaign_invite(request, pk):
    brand = get_request_brand(request)
    campaign = get_object_or_404(MarketingCampaign, pk=pk, brand=brand)
    if not user_can_edit_campaign(request.user, campaign):
        return HttpResponseForbidden('Not allowed')
    form = CampaignCollaboratorInviteForm(request.POST)
    if form.is_valid():
        user = form.cleaned_data['username']
        role = form.cleaned_data['role']
        can_edit = form.cleaned_data['can_edit']
        can_publish = form.cleaned_data['can_publish']
        invite_message = (form.cleaned_data.get('invite_message') or '').strip()
        if not invite_message:
            invite_message = (
                f'{request.user.get_full_name() or request.user.username} invited you '
                f'to collaborate on "{campaign.title}".'
            )
        if role == 'creator':
            can_edit = True
        is_self = user == request.user
        CampaignCollaborator.objects.update_or_create(
            campaign=campaign,
            user=user,
            defaults={
                'role': role,
                'can_edit': can_edit,
                'can_publish': can_publish,
                'accepted': is_self,
                'invite_message': invite_message,
                'is_read': False,
                'invited_by': request.user,
            },
        )
        messages.success(request, f'Invited {user.username}.')
    else:
        messages.error(request, 'Could not invite collaborator.')
    return redirect('campaign_detail', pk=campaign.pk)


@login_required
@require_POST
def campaign_accept_invite(request, pk):
    collab = get_object_or_404(
        CampaignCollaborator.objects.select_related('campaign'),
        pk=pk,
        user=request.user,
    )
    if collab.campaign.brand_id != get_request_brand(request).id:
        return HttpResponseForbidden('Not allowed')
    collab.accepted = True
    collab.is_read = True
    collab.save(update_fields=['accepted', 'is_read'])
    messages.success(request, 'Invitation accepted.')
    return redirect('campaign_detail', pk=collab.campaign_id)


@login_required
@require_POST
def campaign_decline_invite(request, pk):
    collab = get_object_or_404(
        CampaignCollaborator.objects.select_related('campaign'),
        pk=pk,
        user=request.user,
        accepted=False,
    )
    if collab.campaign.brand_id != get_request_brand(request).id:
        return HttpResponseForbidden('Not allowed')
    if collab.role == 'owner':
        return HttpResponseForbidden('Not allowed')
    collab.delete()
    messages.success(request, 'Invitation declined.')
    return redirect('marketing')


@login_required
@require_POST
def campaign_log_content(request, pk):
    brand = get_request_brand(request)
    campaign = get_object_or_404(MarketingCampaign, pk=pk, brand=brand)
    if not user_can_view_campaign(request.user, campaign):
        return HttpResponseForbidden('Not allowed')
    can_log = (
        user_can_edit_campaign(request.user, campaign)
        or campaign.collaborators.filter(user=request.user, accepted=True).exists()
        or campaign.property.owner_id == request.user.id
    )
    if not can_log:
        return HttpResponseForbidden('Not allowed')
    form = CampaignContentLogForm(request.POST)
    if form.is_valid():
        today = timezone.localdate()
        CampaignContentLog.objects.update_or_create(
            campaign=campaign,
            user=request.user,
            work_date=today,
            defaults={
                'photos_count': form.cleaned_data['photos_count'],
                'videos_count': form.cleaned_data['videos_count'],
                'note': form.cleaned_data.get('note') or '',
            },
        )
        messages.success(request, 'Today\'s photo/video posts saved.')
        if campaign.should_auto_complete():
            campaign.status = 'completed'
            campaign.save(update_fields=['status', 'updated_at'])
            messages.info(request, 'All posts done and end date passed — campaign marked completed.')
    else:
        messages.error(request, 'Could not save content log.')
    return redirect('campaign_detail', pk=campaign.pk)


@login_required
@require_POST
def campaign_task_message_read(request, pk):
    msg = get_object_or_404(
        CampaignTaskMessage,
        pk=pk,
        recipient=request.user,
    )
    if msg.campaign.brand_id != get_request_brand(request).id:
        return HttpResponseForbidden('Not allowed')
    msg.is_read = True
    msg.save(update_fields=['is_read'])
    return redirect('campaign_detail', pk=msg.campaign_id)


@login_required
@privilege_required('view_dashboard')
def dashboard(request):
    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    rent_props = props.filter(listing_type='rent')
    sale_count = props.filter(listing_type='sale').count()
    total_rent = rent_props.aggregate(total=Sum('monthly_rent'))['total'] or Decimal('0')
    total_advance = rent_props.aggregate(total=Sum('advance_amount'))['total'] or Decimal('0')
    occupied = rent_props.filter(is_occupied=True).count()
    vacant = rent_props.filter(is_occupied=False).count()
    unread_enquiries = Enquiry.objects.filter(
        property__in=props, is_read=False
    ).count()
    open_complaints = Complaint.objects.filter(
        property__in=props, status__in=['open', 'in_progress']
    ).count()
    due_properties = properties_missing_rent_for_month(request.user, brand=brand)
    today = timezone.localdate()
    income, expenses, net = income_expense_for_month(request.user, today.year, today.month, brand=brand)

    recent_payments = (
        RentPayment.objects.filter(property__in=rent_props)
        .select_related('property', 'tenant')[:8]
    )

    from django.urls import reverse
    from django.utils.safestring import mark_safe

    from accounts.ui_components import build_button, build_empty, build_kpis, build_page_header, build_popup
    from accounts.ui_table import build_table

    property_count = props.count()
    month_label = f'{month_name[today.month]} {today.year}'
    dashboard_kpis = build_kpis(
        [
            {'label': 'Properties', 'value': property_count, 'href': reverse('my_properties')},
            {'label': 'For sale', 'value': sale_count},
            {'label': 'Monthly rent (total)', 'value': f'₹{total_rent:,.0f}'},
            {'label': 'Advance held', 'value': f'₹{total_advance:,.0f}'},
            {'label': 'Occupied / Vacant', 'value': f'{occupied} / {vacant}'},
            {'label': f'{month_label} net', 'value': f'₹{net:,.0f}'},
            {
                'label': 'Unread enquiries',
                'value': unread_enquiries,
                'tone': 'warn' if unread_enquiries else '',
                'href': reverse('enquiries_inbox'),
            },
            {
                'label': 'Open complaints',
                'value': open_complaints,
                'tone': 'danger' if open_complaints else '',
            },
            {
                'label': 'Rent due this month',
                'value': len(due_properties),
                'tone': 'warn' if due_properties else 'ok',
            },
        ]
    )

    dashboard_help_popup = build_popup(
        'dashboard-help',
        title='Dashboard guide',
        body=(
            'KPIs show portfolio health. Use Rent due to record missing payments, '
            'and Enquiries for messages from public listings.'
        ),
        cancel_label='Got it',
    )
    page_header = build_page_header(
        'Your dashboard',
        subtitle='Private view of rent, advance, due months, and enquiries.',
        tooltip='Portfolio snapshot: rent due, occupancy, enquiries, and recent payments.',
        actions=[
            build_button('Reports', href=reverse('reports'), variant='secondary'),
            build_button('Add property', href=reverse('property_create'), variant='primary'),
            build_button('Send month rent reminder', variant='secondary', open_popup='rent-reminder'),
            build_button('How this works', variant='secondary', open_popup='dashboard-help'),
        ],
    )

    due_rows = []
    for property in due_properties:
        due_rows.append(
            {
                'property': mark_safe(
                    f'{property.title}<br><span class="meta">{property.city}</span>'
                ),
                'expected': f'₹{property.monthly_rent:,.0f}',
                'actions': mark_safe(
                    f'<a class="btn btn-primary btn-sm" href="{reverse("payment_add", args=[property.pk])}">Record payment</a>'
                ),
            }
        )
    due_table = build_table(
        id='due-rent',
        columns=[
            {'key': 'property', 'label': 'Property', 'html': True},
            {'key': 'expected', 'label': 'Expected'},
            {'key': 'actions', 'label': '', 'html': True, 'width': '140px'},
        ],
        rows=due_rows,
        empty_text='No rent due.',
    )

    prop_rows = []
    for property in props[:12]:
        if property.is_for_sale:
            status = property.get_sale_status_display()
            price_label = property.display_price
            advance_label = '—'
        else:
            status = 'Occupied' if property.is_occupied else 'Vacant'
            price_label = f'₹{property.monthly_rent:,.0f}' if property.monthly_rent else '—'
            advance_label = f'₹{property.advance_amount:,.0f}'
        prop_rows.append(
            {
                'property': mark_safe(
                    f'<a href="{reverse("property_manage", args=[property.pk])}">{property.title}</a>'
                    f'<br><span class="meta">{property.city} · {property.get_listing_type_display()}</span>'
                ),
                'rent': price_label,
                'advance': advance_label,
                'status': status,
            }
        )
    properties_table = build_table(
        id='dash-properties',
        columns=[
            {'key': 'property', 'label': 'Property', 'html': True},
            {'key': 'rent', 'label': 'Price'},
            {'key': 'advance', 'label': 'Advance'},
            {'key': 'status', 'label': 'Status', 'badge': True},
        ],
        rows=prop_rows,
        empty_text='No properties yet.',
    )

    pay_rows = []
    for payment in recent_payments:
        pay_rows.append(
            {
                'property': mark_safe(
                    f'{payment.property.title}<br><span class="meta">{payment.month_for.strftime("%b %Y")}</span>'
                ),
                'amount': f'₹{payment.amount:,.0f}',
                'status': payment.get_status_display(),
            }
        )
    payments_table = build_table(
        id='dash-payments',
        columns=[
            {'key': 'property', 'label': 'Property', 'html': True},
            {'key': 'amount', 'label': 'Amount'},
            {'key': 'status', 'label': 'Status', 'badge': True},
        ],
        rows=pay_rows,
        empty_text='No rent payments recorded yet.',
    )

    reminder_tenants = (
        Tenant.objects.filter(property__in=rent_props, is_active=True)
        .select_related('property', 'user')
        .order_by('name')
    )
    reminder_rows = ''.join(
        (
            '<label class="checkbox-row" style="display:flex;gap:0.5rem;margin:0.35rem 0">'
            f'<input type="checkbox" name="tenants" value="{tenant.pk}" checked>'
            f'<span>{tenant.name} · {tenant.property.title}'
            f'{" (no login)" if not tenant.user_id else ""}</span></label>'
        )
        for tenant in reminder_tenants
    ) or '<p class="meta">No active tenants yet.</p>'
    reminder_body = (
        '<p class="meta">Select tenants. The reminder is delivered to each tenant inbox.</p>'
        + reminder_rows
        + '<label for="id_reminder_message" style="display:block;margin-top:0.85rem">Message</label>'
        + '<textarea id="id_reminder_message" name="message" rows="4">'
        'This is a reminder to pay this month’s rent. Please check your tenant portal.'
        '</textarea>'
    )
    rent_reminder_popup = build_popup(
        'rent-reminder',
        title='Send month rent reminder',
        body=mark_safe(reminder_body),
        body_html=True,
        form_action=reverse('rent_reminder_send'),
        confirm_label='Send reminder',
        cancel_label='Cancel',
        size='lg',
    )

    return render(
        request,
        'properties/dashboard.html',
        {
            'properties': props,
            'total_rent': total_rent,
            'total_advance': total_advance,
            'occupied': occupied,
            'vacant': vacant,
            'recent_payments': recent_payments,
            'property_count': property_count,
            'due_properties': due_properties,
            'unread_enquiries': unread_enquiries,
            'open_complaints': open_complaints,
            'month_income': income,
            'month_expenses': expenses,
            'month_net': net,
            'month_label': month_label,
            'dashboard_kpis': dashboard_kpis,
            'dashboard_help_popup': dashboard_help_popup,
            'page_header': page_header,
            'due_table': due_table,
            'properties_table': properties_table,
            'payments_table': payments_table,
            'properties_empty': build_empty(
                'No properties yet.',
                action_label='Add one',
                action_href=reverse('property_create'),
            ),
            'payments_empty': build_empty('No rent payments recorded yet.'),
            'properties_panel_actions': [
                build_button('View all', href=reverse('my_properties'), variant='secondary', size='sm'),
            ],
            'rent_reminder_popup': rent_reminder_popup,
        },
    )


@login_required
@privilege_required('manage_rent_reminders')
@require_POST
def rent_reminder_send(request):
    from .notifications import notify_user

    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    tenants = Tenant.objects.filter(property__in=props, is_active=True).select_related('property', 'user')
    form = RentReminderForm(request.POST, tenants=tenants)
    if not form.is_valid():
        messages.error(request, 'Select at least one tenant and enter a message.')
        return redirect('dashboard')
    sent = 0
    skipped = 0
    body = form.cleaned_data['message']
    for tenant in form.cleaned_data['tenants']:
        if not tenant.user_id:
            skipped += 1
            continue
        notify_user(
            user=tenant.user,
            brand=brand,
            kind='rent_reminder',
            title=body[:200],
            url=reverse('tenant_portal'),
        )
        sent += 1
    if sent:
        messages.success(request, f'Rent reminder sent to {sent} tenant inbox{"es" if sent != 1 else ""}.')
    if skipped:
        messages.info(request, f'{skipped} tenant(s) have no login yet, so they did not get an inbox message.')
    if not sent and not skipped:
        messages.info(request, 'No tenants selected.')
    return redirect('dashboard')


@login_required
@privilege_required('manage_properties')
def my_properties(request):
    from django.urls import reverse

    from accounts.ui_components import build_button, build_empty, build_listing, build_listings, build_page_header, build_popup
    from django.utils.safestring import mark_safe

    props = Property.for_user(request.user, brand=get_request_brand(request)).prefetch_related('tenants', 'payments', 'images')
    cards = []
    for prop in props:
        tenant = prop.current_tenant
        if prop.is_for_sale:
            lines = [prop.get_sale_status_display(), f'Furnishing: {prop.get_furnishing_display()}']
            price = prop.display_price
            badges = [
                {'label': 'For sale', 'tone': 'sale'},
                {'label': 'Public' if prop.is_listed_publicly else 'Private', 'tone': ''},
            ]
        else:
            lines = [f'Advance ₹{prop.advance_amount:,.0f}']
            if tenant:
                lines.append(f'Tenant: {tenant.name}')
            if prop.planned_vacate_date:
                lines.append(f'Vacating {prop.planned_vacate_date:%d %b %Y}')
            price = f'Rent ₹{prop.monthly_rent:,.0f}' if prop.monthly_rent else '—'
            badges = [
                {'label': 'Public' if prop.is_listed_publicly else 'Private', 'tone': ''},
                {
                    'label': 'Occupied' if prop.is_occupied else 'Vacant',
                    'tone': 'occupied' if prop.is_occupied else 'vacant',
                },
            ]
        listing_actions = [
            build_button('Manage', href=reverse('property_manage', args=[prop.pk]), variant='primary', size='sm'),
            build_button('Edit', href=reverse('property_edit', args=[prop.pk]), variant='secondary', size='sm'),
        ]
        if prop.is_for_rent:
            listing_actions.append(
                build_button(
                    'Vacant',
                    variant='secondary',
                    size='sm',
                    open_popup=f'vacate-{prop.pk}',
                )
            )
        cards.append(
            build_listing(
                prop.title,
                href=reverse('property_manage', args=[prop.pk]),
                meta=f'{prop.city} · {prop.get_listing_type_display()}',
                price=price,
                badges=badges,
                lines=lines,
                actions=listing_actions,
            )
        )
    vacate_popups = []
    for prop in props:
        if not prop.is_for_rent:
            continue
        initial = prop.planned_vacate_date.isoformat() if prop.planned_vacate_date else ''
        vacate_popups.append(
            build_popup(
                f'vacate-{prop.pk}',
                title=f'Vacate date — {prop.title}',
                body=mark_safe(
                    '<p class="meta">Choose the future date when the tenant will vacate this home.</p>'
                    '<label for="id_planned_vacate_date">Vacate date</label>'
                    f'<input type="date" name="planned_vacate_date" id="id_planned_vacate_date" required value="{initial}">'
                ),
                body_html=True,
                form_action=reverse('property_vacate', args=[prop.pk]),
                confirm_label='Save date',
                cancel_label='Cancel',
            )
        )
    return render(
        request,
        'properties/my_properties.html',
        {
            'properties': props,
            'page_header': build_page_header(
                'My properties',
                subtitle='Private data: rent, advance, tenants, and payments.',
                actions=[build_button('Add property', href=reverse('property_create'), variant='primary')],
            ),
            'listing_cards': build_listings(cards),
            'listings_empty': build_empty(
                'You have not added any properties.',
                action_label='Add your first one',
                action_href=reverse('property_create'),
            ),
            'vacate_popups': vacate_popups,
        },
    )


@login_required
@privilege_required('manage_properties')
def property_create(request):
    from .models import ensure_default_amenities

    ensure_default_amenities()
    brand = get_request_brand(request)
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, user=request.user, brand=brand)
        if form.is_valid():
            prop = form.save(commit=False)
            prop.owner = request.user
            assign_brand(prop, brand)
            if prop.building_id is None and form.cleaned_data.get('building'):
                prop.building = form.cleaned_data['building']
            prop.save()
            form.save_m2m()
            form._save_other_amenity(prop)
            messages.success(request, 'Property added. You can add a tenant next, or go back to the listing.')
            return redirect('property_manage', pk=prop.pk)
    else:
        form = PropertyForm(user=request.user, brand=brand)
    return render(request, 'properties/property_form.html', {'form': form, 'mode': 'add'})


@login_required
@privilege_required('manage_properties')
def property_edit(request, pk):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    if request.method == 'POST':
        form = PropertyForm(
            request.POST,
            request.FILES,
            instance=prop,
            user=request.user,
            brand=get_request_brand(request),
        )
        if form.is_valid():
            form.save()
            messages.success(request, 'Property updated.')
            return redirect('property_manage', pk=prop.pk)
    else:
        form = PropertyForm(instance=prop, user=request.user, brand=get_request_brand(request))
    return render(
        request,
        'properties/property_form.html',
        {'form': form, 'mode': 'edit', 'property': prop},
    )


@login_required
def property_delete(request, pk):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, owner=request.user, brand=brand)
    if request.method == 'POST':
        prop.delete()
        messages.success(request, 'Property deleted.')
        return redirect('my_properties')
    return render(request, 'properties/property_confirm_delete.html', {'property': prop})


@login_required
@privilege_required('manage_properties')
def property_manage(request, pk):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    prop = Property.objects.select_related('building').prefetch_related(
        'tenants', 'payments', 'images', 'expenses', 'complaints', 'shares__user', 'amenities'
    ).get(pk=prop.pk)

    payments = prop.payments.select_related('tenant')
    paid_total = payments.filter(status='paid').aggregate(total=Sum('amount'))['total'] or Decimal('0')
    expense_total = prop.expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')

    from accounts.components import build_kpis, build_page_header
    from .forms import DocumentForm, MeterReadingForm

    subtitle_bits = []
    if prop.building_id:
        subtitle_bits.append(prop.building.name)
    if prop.unit_number:
        subtitle_bits.append(f'Unit {prop.unit_number}')
    if prop.door_number:
        subtitle_bits.append(f'Door {prop.door_number}')
    city_line = f'{prop.address}, {prop.city}'
    if prop.pincode:
        city_line += f' {prop.pincode}'
    subtitle_bits.append(city_line)

    actions = [
        {'label': 'Back to properties', 'href': reverse('my_properties'), 'variant': 'secondary', 'size': 'sm'},
        {'label': 'Edit', 'href': reverse('property_edit', args=[prop.pk]), 'variant': 'secondary', 'size': 'sm'},
    ]
    is_owner = prop.owner_id == request.user.id
    if is_owner:
        actions.append(
            {'label': 'Delete', 'href': reverse('property_delete', args=[prop.pk]), 'variant': 'danger', 'size': 'sm'}
        )
    actions.extend(
        [
            {'label': 'Messages', 'href': reverse('thread_view', args=[prop.pk]), 'variant': 'secondary', 'size': 'sm'},
            {
                'label': 'Add document',
                'href': reverse('document_add', args=[prop.pk]),
                'variant': 'secondary',
                'size': 'sm',
            },
            {
                'label': 'Meter reading',
                'href': reverse('meter_add', args=[prop.pk]),
                'variant': 'secondary',
                'size': 'sm',
            },
        ]
    )
    if prop.is_for_sale:
        kpi_items = [
            {'label': 'Sale price', 'value': prop.display_price},
            {'label': 'Status', 'value': prop.get_sale_status_display()},
            {'label': 'Furnishing', 'value': prop.get_furnishing_display()},
            {'label': 'Expenses (all time)', 'value': f'₹{expense_total:.0f}'},
        ]
    else:
        kpi_items = [
            {'label': 'Monthly rent', 'value': f'₹{prop.monthly_rent:.0f}'},
            {'label': 'Advance / deposit', 'value': f'₹{prop.advance_amount:.0f}'},
            {'label': 'Rent collected (paid)', 'value': f'₹{paid_total:.0f}'},
            {'label': 'Expenses (all time)', 'value': f'₹{expense_total:.0f}'},
        ]

    return render(
        request,
        'properties/property_manage.html',
        {
            'property': prop,
            'tenants': prop.tenants.all(),
            'payments': payments,
            'paid_total': paid_total,
            'expense_total': expense_total,
            'expenses': prop.expenses.all()[:20],
            'images': prop.images.all(),
            'complaints': prop.complaints.all()[:20],
            'shares': prop.shares.select_related('user'),
            'current_tenant': prop.current_tenant,
            'image_form': PropertyImageForm(),
            'expense_form': ExpenseForm(),
            'share_form': PropertyShareForm(),
            'is_owner': is_owner,
            'documents': prop.documents.all()[:20],
            'meters': prop.meter_readings.all()[:10],
            'document_form': DocumentForm(property_obj=prop),
            'meter_form': MeterReadingForm(initial={'reading_date': timezone.localdate()}),
            'join_requests': prop.join_requests.filter(status='pending').select_related('user'),
            'amenity_labels': [
                label
                for label in prop.amenities.exclude(code='others').values_list('label', flat=True)
            ],
            'page_header': build_page_header(
                prop.title,
                subtitle=' · '.join(subtitle_bits),
                actions=actions,
            ),
            'kpis': build_kpis(kpi_items),
        },
    )


@login_required
def tenant_add(request, pk):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    if prop.is_for_sale:
        messages.error(request, 'Tenants cannot be added to sale listings.')
        return redirect('property_manage', pk=prop.pk)
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES)
        if form.is_valid():
            tenant = form.save(commit=False)
            tenant.property = prop
            tenant.save()
            apply_tenant_login_fields(tenant, form, brand=get_request_brand(request))
            if tenant.is_active:
                prop.is_occupied = True
                prop.save(update_fields=['is_occupied'])
            messages.success(request, 'Tenant added.')
            return redirect('property_manage', pk=prop.pk)
    else:
        form = TenantForm(initial={'is_active': True, 'advance_paid': prop.advance_amount})
    return render(
        request,
        'properties/tenant_form.html',
        {'form': form, 'property': prop, 'mode': 'add'},
    )


@login_required
def tenant_edit(request, pk, tenant_id):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    tenant = get_object_or_404(Tenant, pk=tenant_id, property=prop)
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES, instance=tenant)
        if form.is_valid():
            form.save()
            apply_tenant_login_fields(tenant, form, brand=get_request_brand(request))
            prop.is_occupied = prop.tenants.filter(is_active=True).exists()
            prop.save(update_fields=['is_occupied'])
            messages.success(request, 'Tenant updated.')
            return redirect('property_manage', pk=prop.pk)
    else:
        form = TenantForm(instance=tenant)
    return render(
        request,
        'properties/tenant_form.html',
        {'form': form, 'property': prop, 'mode': 'edit', 'tenant': tenant},
    )


@login_required
@privilege_required('manage_tenants')
def tenant_create_login(request, pk, tenant_id):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    tenant = get_object_or_404(Tenant, pk=tenant_id, property=prop)
    if tenant.user_id:
        messages.info(request, f'This tenant already has login: {tenant.user.username}')
        return redirect('tenant_edit', pk=prop.pk, tenant_id=tenant.pk)
    if request.method == 'POST':
        form = TenantLoginForm(request.POST)
        if form.is_valid():
            create_login_for_tenant(
                tenant,
                form.cleaned_data['username'],
                form.cleaned_data['password'],
                brand=get_request_brand(request),
                email=tenant.email,
            )
            messages.success(
                request,
                f'Login created. Username: {form.cleaned_data["username"]}. Share this password with the tenant.',
            )
            return redirect('property_manage', pk=prop.pk)
    else:
        form = TenantLoginForm(initial={'username': (tenant.email or tenant.name or 'tenant').split('@')[0][:150]})
    return render(
        request,
        'properties/tenant_login_form.html',
        {'form': form, 'property': prop, 'tenant': tenant},
    )


@login_required
@privilege_required('manage_properties')
@require_POST
def property_vacate(request, pk):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    form = PlannedVacateForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Pick a future vacate date.')
        return redirect('my_properties')
    prop.planned_vacate_date = form.cleaned_data['planned_vacate_date']
    tenant = prop.current_tenant
    if tenant:
        tenant.lease_end_date = prop.planned_vacate_date
        tenant.save(update_fields=['lease_end_date'])
    prop.save(update_fields=['planned_vacate_date'])
    messages.success(request, f'Vacate date set to {prop.planned_vacate_date:%d %b %Y}.')
    return redirect('my_properties')


@login_required
@privilege_required('manage_tenants')
@require_POST
def join_request_review(request, pk, request_id):
    from .notifications import notify_user

    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    join = get_object_or_404(TenantJoinRequest, pk=request_id, property=prop)
    action = request.POST.get('action')
    if join.status != 'pending':
        messages.info(request, 'That request was already reviewed.')
        return redirect('property_manage', pk=prop.pk)
    join.reviewed_at = timezone.now()
    if action == 'accept':
        if prop.is_occupied and prop.current_tenant and prop.current_tenant.user_id != join.user_id:
            messages.error(request, 'This property already has an active tenant.')
            return redirect('property_manage', pk=prop.pk)
        join.status = 'accepted'
        join.save(update_fields=['status', 'reviewed_at'])
        tenant = Tenant.objects.create(
            property=prop,
            user=join.user,
            name=join.user.get_full_name() or join.user.username,
            email=join.user.email or '',
            is_active=True,
            move_in_date=timezone.localdate(),
        )
        prop.is_occupied = True
        prop.save(update_fields=['is_occupied'])
        notify_user(
            user=join.user,
            brand=get_request_brand(request),
            kind='join_request',
            title=f'You were added to {prop.title}',
            url=reverse('tenant_portal'),
        )
        messages.success(request, f'{tenant.name} was added to this property.')
    else:
        join.status = 'rejected'
        join.save(update_fields=['status', 'reviewed_at'])
        notify_user(
            user=join.user,
            brand=get_request_brand(request),
            kind='join_request',
            title=f'Request to join {prop.title} was declined',
            url=reverse('public_detail', args=[prop.pk]),
        )
        messages.info(request, 'Join request declined.')
    return redirect('property_manage', pk=prop.pk)


@login_required
@privilege_required('manage_payments')
def payment_add(request, pk):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    if prop.is_for_sale:
        messages.error(request, 'Rent payments do not apply to sale listings.')
        return redirect('property_manage', pk=prop.pk)
    if request.method == 'POST':
        form = RentPaymentForm(request.POST, property_obj=prop)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.property = prop
            if payment.due_date is None:
                payment.due_date = payment.month_for.replace(day=min(payment.month_for.day, 28))
            if (
                payment.status == 'paid'
                and prop.late_fee_amount
                and payment.due_date
                and payment.payment_date
                and payment.payment_date
                > payment.due_date + timedelta(days=prop.late_fee_grace_days or 0)
            ):
                if not payment.late_fee:
                    payment.late_fee = prop.late_fee_amount
            payment.save()
            messages.success(request, 'Rent payment recorded.')
            return redirect('payment_receipt', pk=prop.pk, payment_id=payment.pk)
    else:
        form = RentPaymentForm(
            property_obj=prop,
            initial={
                'amount': prop.monthly_rent,
                'tenant': prop.current_tenant,
                'payment_date': timezone.localdate(),
                'month_for': month_start(),
            },
        )
    return render(
        request,
        'properties/payment_form.html',
        {'form': form, 'property': prop},
    )


@login_required
def payment_delete(request, pk, payment_id):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    payment = get_object_or_404(RentPayment, pk=payment_id, property=prop)
    if request.method == 'POST':
        payment.delete()
        messages.success(request, 'Payment removed.')
    return redirect('property_manage', pk=prop.pk)


def _can_view_payment(request, prop, payment):
    brand = get_request_brand(request)
    if prop.user_can_manage(request.user, brand=brand):
        return True
    if payment.tenant_id and payment.tenant.user_id == request.user.id:
        return True
    return False


@login_required
def payment_receipt(request, pk, payment_id):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, brand=brand)
    payment = get_object_or_404(RentPayment, pk=payment_id, property=prop)
    if not _can_view_payment(request, prop, payment):
        return HttpResponseForbidden('Not allowed')
    return render(
        request,
        'properties/payment_receipt.html',
        {'property': prop, 'payment': payment},
    )


@login_required
def payment_receipt_pdf(request, pk, payment_id):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, brand=brand)
    payment = get_object_or_404(RentPayment, pk=payment_id, property=prop)
    if not _can_view_payment(request, prop, payment):
        return HttpResponseForbidden('Not allowed')

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError:
        messages.warning(request, 'PDF library missing. Showing printable receipt instead.')
        return redirect('payment_receipt', pk=pk, payment_id=payment_id)

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 80
    pdf.setFont('Helvetica-Bold', 18)
    pdf.drawString(50, y, 'PropKeep — Rent Receipt')
    y -= 40
    pdf.setFont('Helvetica', 12)
    lines = [
        f'Receipt #: {payment.pk}',
        f'Property: {prop.title}',
        f'Address: {prop.address}, {prop.city}',
        f'Tenant: {payment.tenant.name if payment.tenant else "-"}',
        f'Month: {payment.month_for:%B %Y}',
        f'Amount: INR {payment.amount}',
        f'Status: {payment.get_status_display()}',
        f'Payment date: {payment.payment_date}',
        f'Notes: {payment.notes or "-"}',
        f'Issued to owner: {prop.owner.get_username()}',
    ]
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 22
    pdf.showPage()
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rent-receipt-{payment.pk}.pdf"'
    return response


@login_required
@require_POST
def image_add(request, pk):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    form = PropertyImageForm(request.POST, request.FILES)
    if form.is_valid():
        image = form.save(commit=False)
        image.property = prop
        if image.is_cover:
            prop.images.update(is_cover=False)
        image.save()
        messages.success(request, 'Photo uploaded.')
    else:
        messages.error(request, 'Could not upload photo. Check the file type.')
    return redirect('property_manage', pk=prop.pk)


@login_required
@require_POST
def image_delete(request, pk, image_id):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    image = get_object_or_404(PropertyImage, pk=image_id, property=prop)
    image.delete()
    messages.success(request, 'Photo deleted.')
    return redirect('property_manage', pk=prop.pk)


@login_required
@require_POST
def expense_add(request, pk):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    form = ExpenseForm(request.POST)
    if form.is_valid():
        expense = form.save(commit=False)
        expense.property = prop
        expense.save()
        messages.success(request, 'Expense recorded.')
    else:
        messages.error(request, 'Could not save expense.')
    return redirect('property_manage', pk=prop.pk)


@login_required
@require_POST
def expense_delete(request, pk, expense_id):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    expense = get_object_or_404(Expense, pk=expense_id, property=prop)
    expense.delete()
    messages.success(request, 'Expense deleted.')
    return redirect('property_manage', pk=prop.pk)


@login_required
@privilege_required('view_enquiries')
def enquiries_inbox(request):
    from django.middleware.csrf import get_token
    from django.urls import reverse
    from django.utils.safestring import mark_safe

    from accounts.ui_table import build_table

    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    enquiries = list(
        Enquiry.objects.filter(property__in=props, brand=brand).select_related('property')
    )
    unread = sum(1 for e in enquiries if not e.is_read)
    csrf = get_token(request)
    rows = []
    for enquiry in enquiries:
        prop_url = reverse('property_manage', args=[enquiry.property_id])
        if enquiry.is_read:
            actions = '<span class="badge">Read</span>'
        else:
            action_url = reverse('enquiry_mark_read', args=[enquiry.pk])
            actions = (
                f'<form method="post" action="{action_url}">'
                f'<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">'
                f'<button class="btn btn-secondary btn-sm" type="submit">Mark read</button>'
                f'</form>'
            )
        contact = enquiry.email
        if enquiry.phone:
            contact = f'{enquiry.email} · {enquiry.phone}'
        rows.append(
            {
                'when': enquiry.created_at.strftime('%d %b %Y %H:%M'),
                'type': enquiry.get_enquiry_type_display(),
                'status': enquiry.get_status_display(),
                'property': mark_safe(f'<a href="{prop_url}">{enquiry.property.title}</a>'),
                'from': mark_safe(
                    f'{enquiry.name}<br><span class="meta">{contact}</span>'
                ),
                'message': enquiry.message,
                'actions': mark_safe(
                    f'<a class="btn btn-secondary btn-sm" href="{reverse("lead_detail", args=[enquiry.pk])}">Open</a> {actions}'
                ),
            }
        )
    enquiries_table = build_table(
        id='enquiries',
        columns=[
            {'key': 'when', 'label': 'When', 'width': '140px'},
            {'key': 'type', 'label': 'Type', 'width': '100px', 'badge': True},
            {'key': 'status', 'label': 'Status', 'width': '120px', 'badge': True},
            {'key': 'property', 'label': 'Property', 'width': '18%', 'html': True},
            {'key': 'from', 'label': 'From', 'width': '20%', 'html': True},
            {'key': 'message', 'label': 'Message'},
            {'key': 'actions', 'label': '', 'width': '180px', 'html': True},
        ],
        rows=rows,
        empty_text='No enquiries yet.',
    )
    from accounts.ui_components import build_button, build_kpis, build_page_header, build_popup

    enquiry_kpis = build_kpis(
        [
            {'label': 'Total', 'value': len(rows)},
            {'label': 'Unread', 'value': unread, 'tone': 'warn' if unread else 'ok'},
        ]
    )
    enquiry_help_popup = build_popup(
        'enquiries-help',
        title='Enquiry inbox',
        body='These messages come from the public listings page. Mark them read after you reply outside PropKeep.',
        cancel_label='Close',
    )
    return render(
        request,
        'properties/enquiries.html',
        {
            'enquiries': enquiries,
            'enquiries_table': enquiries_table,
            'enquiry_kpis': enquiry_kpis,
            'enquiry_help_popup': enquiry_help_popup,
            'page_header': build_page_header(
                'Leads',
                subtitle='Rent and sale enquiries — open a lead to schedule visits, log offers, and convert.',
                tooltip='Public visitors send these messages from listing detail pages.',
                actions=[
                    build_button('About inbox', variant='secondary', size='sm', open_popup='enquiries-help'),
                ],
            ),
        },
    )


@login_required
@require_POST
def enquiry_mark_read(request, enquiry_id):
    brand = get_request_brand(request)
    enquiry = get_object_or_404(
        Enquiry,
        pk=enquiry_id,
        brand=brand,
        property__in=Property.for_user(request.user, brand=brand),
    )
    enquiry.is_read = True
    enquiry.save(update_fields=['is_read'])
    return redirect('enquiries_inbox')


@login_required
@privilege_required('view_reports')
def reports(request):
    brand = get_request_brand(request)
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    income, expenses, net = income_expense_for_month(request.user, year, month, brand=brand)
    ytd_income = Decimal('0')
    ytd_expenses = Decimal('0')
    for m in range(1, 13):
        yi, ye, _ = income_expense_for_month(request.user, year, m, brand=brand)
        ytd_income += yi
        ytd_expenses += ye
    props = Property.for_user(request.user, brand=brand).select_related('building')
    by_property = []
    for prop in props:
        p_income = (
            prop.payments.filter(status='paid', month_for__year=year, month_for__month=month)
            .aggregate(total=Sum('amount'))['total']
            or Decimal('0')
        )
        p_expense = (
            prop.expenses.filter(expense_date__year=year, expense_date__month=month)
            .aggregate(total=Sum('amount'))['total']
            or Decimal('0')
        )
        by_property.append(
            {
                'property': prop,
                'building': prop.building.name if prop.building_id else '',
                'income': p_income,
                'expenses': p_expense,
                'net': p_income - p_expense,
            }
        )

    overdue = []
    start = month_start(timezone.localdate())
    for tenant in Tenant.objects.filter(
        property__in=props, is_active=True, brand=brand
    ).select_related('property'):
        paid = tenant.payments.filter(
            month_for__year=start.year,
            month_for__month=start.month,
            status__in=['paid', 'partial'],
        ).exists()
        if not paid:
            overdue.append(tenant)

    from django.utils.safestring import mark_safe

    from accounts.components import build_filter, build_kpis, build_page_header, build_table

    month_choices = [(str(num), name) for num, name in enumerate(month_name[1:], start=1)]
    year_choices = [(str(y), str(y)) for y in range(today.year - 3, today.year + 1)]
    report_rows = []
    for row in by_property:
        prop = row['property']
        report_rows.append(
            {
                'property': mark_safe(
                    f'<a href="{reverse("property_manage", args=[prop.pk])}">{prop.title}</a>'
                ),
                'building': row['building'] or '—',
                'income': f'₹{row["income"]:.0f}',
                'expenses': f'₹{row["expenses"]:.0f}',
                'net': f'₹{row["net"]:.0f}',
            }
        )
    overdue_rows = [
        {
            'tenant': t.name,
            'property': t.property.title,
        }
        for t in overdue
    ]
    return render(
        request,
        'properties/reports.html',
        {
            'year': year,
            'month': month,
            'month_label': f'{month_name[month]} {year}',
            'income': income,
            'expenses': expenses,
            'net': net,
            'ytd_income': ytd_income,
            'ytd_expenses': ytd_expenses,
            'ytd_net': ytd_income - ytd_expenses,
            'by_property': by_property,
            'overdue': overdue,
            'months': list(enumerate(month_name[1:], start=1)),
            'years': range(today.year - 3, today.year + 1),
            'page_header': build_page_header(
                'Income report',
                subtitle='Monthly rent collected vs expenses. Export for your accountant.',
                tooltip='Filter by month, then download CSV for bookkeeping.',
                actions=[
                    {
                        'label': 'Download CSV',
                        'href': f'{reverse("reports_csv")}?year={year}&month={month}',
                        'variant': 'secondary',
                    },
                    {
                        'label': 'GST invoices',
                        'href': f'{reverse("under_construction")}?feature=GST+invoices',
                        'variant': 'secondary',
                    },
                ],
            ),
            'kpis': build_kpis(
                [
                    {'label': f'{month_name[month]} {year} income', 'value': f'₹{income:.0f}'},
                    {'label': 'Expenses', 'value': f'₹{expenses:.0f}'},
                    {'label': 'Net', 'value': f'₹{net:.0f}'},
                    {'label': f'{year} YTD income', 'value': f'₹{ytd_income:.0f}'},
                    {'label': f'{year} YTD net', 'value': f'₹{ytd_income - ytd_expenses:.0f}'},
                ]
            ),
            'report_filter': build_filter(
                [
                    {
                        'name': 'month',
                        'label': 'Month',
                        'type': 'select',
                        'value': str(month),
                        'choices': month_choices,
                    },
                    {
                        'name': 'year',
                        'label': 'Year',
                        'type': 'select',
                        'value': str(year),
                        'choices': year_choices,
                    },
                ],
                submit_label='Show',
            ),
            'property_table': build_table(
                id='report-by-property',
                columns=[
                    {'key': 'property', 'label': 'Property', 'html': True},
                    {'key': 'building', 'label': 'Building'},
                    {'key': 'income', 'label': 'Income', 'align': 'right'},
                    {'key': 'expenses', 'label': 'Expenses', 'align': 'right'},
                    {'key': 'net', 'label': 'Net', 'align': 'right'},
                ],
                rows=report_rows,
                empty_text='No properties.',
            ),
            'overdue_table': build_table(
                id='report-overdue',
                columns=[
                    {'key': 'tenant', 'label': 'Tenant'},
                    {'key': 'property', 'label': 'Property'},
                ],
                rows=overdue_rows,
                empty_text='No overdue tenants this month.',
            ),
        },
    )


@login_required
@require_POST
def share_add(request, pk):
    prop = get_object_or_404(Property, pk=pk, owner=request.user)
    form = PropertyShareForm(request.POST)
    if form.is_valid():
        user = form.cleaned_data['username']
        if user.id == prop.owner_id:
            messages.error(request, 'You already own this property.')
        else:
            PropertyShare.objects.update_or_create(
                property=prop,
                user=user,
                defaults={
                    'role': form.cleaned_data['role'],
                    'commission_percent': form.cleaned_data.get('commission_percent') or 0,
                },
            )
            messages.success(request, f'Shared with {user.username}.')
    else:
        messages.error(request, 'Could not share. Check the username.')
    return redirect('property_manage', pk=prop.pk)


@login_required
@require_POST
def share_remove(request, pk, share_id):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, owner=request.user, brand=brand)
    share = get_object_or_404(PropertyShare, pk=share_id, property=prop)
    share.delete()
    messages.success(request, 'Share removed.')
    return redirect('property_manage', pk=prop.pk)


@login_required
@privilege_required('view_tenant_portal')
def tenant_portal(request):
    from accounts.reminders import unpaid_items_for_user
    from accounts.components import build_kpis, build_page_header, fields_from_django_form
    from .models import Document

    brand = get_request_brand(request)
    profiles = Tenant.objects.filter(
        user=request.user, is_active=True, brand=brand
    ).select_related('property', 'property__building')
    if not profiles.exists():
        messages.info(
            request,
            'No tenant profile is linked to your account yet. Ask the owner/admin to link your login on a tenant record.',
        )
        return render(
            request,
            'properties/tenant_portal.html',
            {
                'profiles': [],
                'payments': [],
                'complaints': [],
                'form': ComplaintForm(),
                'due_items': [],
                'documents': [],
                'pending_payments': [],
                'complaint_fields': fields_from_django_form(ComplaintForm()),
                'page_header': build_page_header(
                    'Tenant portal',
                    subtitle='Due rent, receipts, lease dates, and complaints.',
                ),
                'kpis': build_kpis(
                    [
                        {'label': 'Homes', 'value': 0},
                        {'label': 'Due this month', 'value': 0},
                        {'label': 'Pending pay', 'value': 0},
                    ]
                ),
            },
        )

    complaints = Complaint.objects.filter(tenant__in=profiles).select_related('property')
    payments = RentPayment.objects.filter(tenant__in=profiles).select_related('property')
    due_items = unpaid_items_for_user(request.user, brand=brand)
    pending_payments = payments.filter(status__in=['pending', 'overdue'])
    documents = Document.objects.filter(tenant__in=profiles)
    form = ComplaintForm()

    if request.method == 'POST':
        form = ComplaintForm(request.POST, request.FILES)
        property_id = request.POST.get('property_id')
        tenant = profiles.filter(property_id=property_id).first()
        if form.is_valid() and tenant:
            complaint = form.save(commit=False)
            complaint.property = tenant.property
            complaint.tenant = tenant
            complaint.created_by = request.user
            complaint.save()
            from .notifications import notify_user

            notify_user(
                user=tenant.property.owner,
                brand=brand,
                kind='complaint',
                title=f'Complaint: {complaint.title}',
                url=reverse('complaint_update', args=[tenant.property_id, complaint.pk]),
            )
            messages.success(request, 'Complaint submitted.')
            return redirect('tenant_portal')
        messages.error(request, 'Could not submit complaint.')

    return render(
        request,
        'properties/tenant_portal.html',
        {
            'profiles': profiles,
            'payments': payments[:30],
            'pending_payments': pending_payments,
            'complaints': complaints[:30],
            'form': form,
            'due_items': due_items,
            'documents': documents,
            'complaint_fields': fields_from_django_form(form),
            'page_header': build_page_header(
                'Tenant portal',
                subtitle='Due rent, receipts, lease dates, and complaints.',
            ),
            'kpis': build_kpis(
                [
                    {'label': 'Homes', 'value': profiles.count()},
                    {'label': 'Due this month', 'value': len(due_items)},
                    {'label': 'Pending pay', 'value': pending_payments.count()},
                ]
            ),
        },
    )


@login_required
def complaint_update(request, pk, complaint_id):
    prop = _manageable_property(request, pk)
    if prop is None:
        return HttpResponseForbidden('Not allowed')
    complaint = get_object_or_404(Complaint, pk=complaint_id, property=prop)
    if request.method == 'POST':
        form = ComplaintOwnerForm(request.POST, instance=complaint)
        if form.is_valid():
            form.save()
            messages.success(request, 'Complaint updated.')
            return redirect('property_manage', pk=prop.pk)
    else:
        form = ComplaintOwnerForm(instance=complaint)
    from django.urls import reverse

    return render(
        request,
        'properties/complaint_form.html',
        {
            'form': form,
            'property': prop,
            'complaint': complaint,
            'complaint_subtitle': f'{complaint.title} · {prop.title}',
            'cancel_url': reverse('property_manage', args=[prop.pk]),
        },
    )
