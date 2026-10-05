"""Buildings, leads CRM, inbox, documents, calendar, and related views."""

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import StringIO
import csv
import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_POST

from accounts.brand_scoping import assign_brand, get_request_brand, users_for_brand
from accounts.logging_utils import log_activity
from accounts.privileges import privilege_required
from accounts.ui_components import (
    build_button,
    build_empty,
    build_filter,
    build_kpis,
    build_page_header,
)
from accounts.ui_table import build_table

from .forms import (
    AttachUnitForm,
    BuildingForm,
    DocumentForm,
    LeadStatusForm,
    LeadVisitForm,
    MessageForm,
    MeterReadingForm,
    OfferForm,
    PropertyForm,
    SaleDealForm,
)
from .lead_utils import log_lead_activity
from .models import (
    Amenity,
    Building,
    CommissionPayout,
    Complaint,
    Document,
    Enquiry,
    Expense,
    LeadVisit,
    Message,
    MessageThread,
    MeterReading,
    Offer,
    PaymentOrder,
    Property,
    RentPayment,
    SaleDeal,
    SavedListing,
    Tenant,
    UserNotification,
    ensure_default_amenities,
    income_expense_for_month,
    month_start,
)
from .notifications import notify_user


def _manageable_building(request, pk):
    brand = get_request_brand(request)
    building = get_object_or_404(Building, pk=pk, brand=brand)
    if not building.user_can_manage(request.user, brand=brand):
        return None
    return building


def _leads_qs(request):
    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    return Enquiry.objects.filter(property__in=props, brand=brand).select_related(
        'property', 'property__building', 'assigned_to', 'campaign'
    )


@login_required
@privilege_required('view_buildings')
def building_list(request):
    ensure_default_amenities()
    brand = get_request_brand(request)
    buildings = Building.for_user(request.user, brand=brand).prefetch_related('units')
    rows = []
    for bld in buildings:
        occ = bld.occupancy()
        rows.append(
            {
                'name': mark_safe(
                    f'<a href="{reverse("building_detail", args=[bld.pk])}">{bld.name}</a>'
                ),
                'city': bld.city,
                'units': occ['total'],
                'occupied': occ['occupied'],
                'vacant': occ['vacant'],
                'occ': f'{occ["percent"]}%',
            }
        )
    table = build_table(
        id='buildings',
        columns=[
            {'key': 'name', 'label': 'Building', 'html': True},
            {'key': 'city', 'label': 'City'},
            {'key': 'units', 'label': 'Units'},
            {'key': 'occupied', 'label': 'Occupied'},
            {'key': 'vacant', 'label': 'Vacant'},
            {'key': 'occ', 'label': 'Occupancy'},
        ],
        rows=rows,
        empty_text='No buildings yet. Add a PG or apartment block.',
    )
    vacant = sum(b.occupancy()['vacant'] for b in buildings)
    return render(
        request,
        'properties/buildings.html',
        {
            'page_header': build_page_header(
                'Buildings',
                subtitle='Group units under one address. Standalone listings stay allowed.',
                actions=[
                    build_button('Add building', href=reverse('building_create'), variant='primary'),
                ],
            ),
            'kpis': build_kpis(
                [
                    {'label': 'Buildings', 'value': buildings.count()},
                    {'label': 'Vacant units', 'value': vacant, 'tone': 'warn' if vacant else 'ok'},
                ]
            ),
            'table': table,
        },
    )


@login_required
@privilege_required('manage_buildings')
def building_create(request):
    ensure_default_amenities()
    brand = get_request_brand(request)
    if request.method == 'POST':
        form = BuildingForm(request.POST)
        if form.is_valid():
            building = form.save(commit=False)
            building.owner = request.user
            assign_brand(building, brand)
            building.save()
            form.save_m2m()
            log_activity(request=request, action='create', message=f'Building {building.name}')
            messages.success(request, 'Building created. Add or attach units next.')
            return redirect('building_detail', pk=building.pk)
    else:
        form = BuildingForm()
    return render(
        request,
        'properties/building_form.html',
        {'form': form, 'mode': 'add'},
    )


@login_required
@privilege_required('manage_buildings')
def building_edit(request, pk):
    building = _manageable_building(request, pk)
    if building is None:
        return HttpResponseForbidden('Not allowed')
    if request.method == 'POST':
        form = BuildingForm(request.POST, instance=building)
        if form.is_valid():
            form.save()
            log_activity(request=request, action='update', message=f'Building {building.name}')
            messages.success(request, 'Building updated.')
            return redirect('building_detail', pk=building.pk)
    else:
        form = BuildingForm(instance=building)
    return render(
        request,
        'properties/building_form.html',
        {'form': form, 'mode': 'edit', 'building': building},
    )


@login_required
@privilege_required('view_buildings')
def building_detail(request, pk):
    building = _manageable_building(request, pk)
    if building is None:
        return HttpResponseForbidden('Not allowed')
    brand = get_request_brand(request)
    units = building.units.select_related('owner').order_by('floor_number', 'unit_number', 'title')
    occ = building.occupancy()
    attachable = (
        Property.for_user(request.user, brand=brand)
        .filter(building__isnull=True)
        .order_by('title')
    )
    unit_rows = []
    for unit in units:
        manage_url = reverse('property_manage', args=[unit.pk])
        status = (
            unit.get_sale_status_display()
            if unit.is_for_sale
            else ('Occupied' if unit.is_occupied else 'Vacant')
        )
        unit_rows.append(
            {
                'unit': mark_safe(f'<a href="{manage_url}">{unit.title}</a>'),
                'number': unit.unit_number or unit.door_number or '—',
                'floor': unit.floor_number if unit.floor_number is not None else '—',
                'type': unit.get_listing_type_display(),
                'status': status,
                'price': unit.display_price,
            }
        )
    return render(
        request,
        'properties/building_detail.html',
        {
            'building': building,
            'occupancy': occ,
            'units_table': build_table(
                id='units',
                columns=[
                    {'key': 'unit', 'label': 'Unit', 'html': True},
                    {'key': 'number', 'label': 'No.'},
                    {'key': 'floor', 'label': 'Floor'},
                    {'key': 'type', 'label': 'Listing'},
                    {'key': 'status', 'label': 'Status'},
                    {'key': 'price', 'label': 'Price'},
                ],
                rows=unit_rows,
                empty_text='No units yet. Add a unit or attach an existing listing.',
            ),
            'kpis': build_kpis(
                [
                    {'label': 'Units', 'value': occ['total']},
                    {'label': 'Occupied', 'value': occ['occupied']},
                    {'label': 'Vacant', 'value': occ['vacant'], 'tone': 'warn' if occ['vacant'] else 'ok'},
                    {'label': 'Occupancy', 'value': f'{occ["percent"]}%'},
                ]
            ),
            'page_header': build_page_header(
                building.name,
                subtitle=f'{building.address}, {building.city}',
                actions=[
                    build_button('Edit', href=reverse('building_edit', args=[building.pk]), variant='secondary'),
                    build_button(
                        'Add unit',
                        href=reverse('building_unit_add', args=[building.pk]),
                        variant='primary',
                    ),
                ],
            ),
            'attachable': attachable,
        },
    )


@login_required
@privilege_required('manage_buildings')
def building_unit_add(request, pk):
    building = _manageable_building(request, pk)
    if building is None:
        return HttpResponseForbidden('Not allowed')
    brand = get_request_brand(request)
    initial = {
        'building': building,
        'address': building.address,
        'city': building.city,
        'state': building.state,
        'pincode': building.pincode,
        'country': building.country,
        'street': building.street,
        'landmark': building.landmark,
        'latitude': building.latitude,
        'longitude': building.longitude,
        'year_of_building': building.year_of_building,
    }
    if request.method == 'POST':
        form = PropertyForm(request.POST, request.FILES, user=request.user, brand=brand)
        if form.is_valid():
            prop = form.save(commit=False)
            prop.owner = request.user
            prop.building = building
            assign_brand(prop, brand)
            if not prop.address:
                prop.address = building.address
            if not prop.city:
                prop.city = building.city
            prop.save()
            form.save_m2m()
            form._save_other_amenity(prop)
            messages.success(request, 'Unit added to building.')
            return redirect('building_detail', pk=building.pk)
    else:
        form = PropertyForm(initial=initial, user=request.user, brand=brand)
    return render(
        request,
        'properties/property_form.html',
        {'form': form, 'mode': 'add', 'building': building},
    )


@login_required
@privilege_required('manage_buildings')
@require_POST
def building_unit_attach(request, pk):
    building = _manageable_building(request, pk)
    if building is None:
        return HttpResponseForbidden('Not allowed')
    brand = get_request_brand(request)
    form = AttachUnitForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Could not attach that listing.')
        return redirect('building_detail', pk=building.pk)
    prop = get_object_or_404(
        Property.for_user(request.user, brand=brand),
        pk=form.cleaned_data['property_id'],
        building__isnull=True,
    )
    prop.building = building
    if form.cleaned_data.get('unit_number'):
        prop.unit_number = form.cleaned_data['unit_number']
    if form.cleaned_data.get('floor_number') is not None:
        prop.floor_number = form.cleaned_data['floor_number']
    prop.save()
    messages.success(request, f'Attached {prop.title}.')
    return redirect('building_detail', pk=building.pk)


@login_required
@privilege_required('view_enquiries')
def lead_detail(request, pk):
    brand = get_request_brand(request)
    enquiry = get_object_or_404(_leads_qs(request), pk=pk)
    if not enquiry.is_read:
        enquiry.is_read = True
        enquiry.save(update_fields=['is_read'])
    users = users_for_brand(brand)
    props = Property.for_user(request.user, brand=brand)
    if enquiry.property.building_id:
        props = props.filter(
            Q(pk=enquiry.property_id) | Q(building_id=enquiry.property.building_id)
        )
    else:
        props = props.filter(pk=enquiry.property_id)
    status_form = LeadStatusForm(instance=enquiry, users=users)
    visit_form = LeadVisitForm(properties=props, initial={'property': enquiry.property})
    offer_form = OfferForm(
        initial={'offer_type': 'sale' if enquiry.property.is_for_sale else 'rent'}
    )
    deal_form = SaleDealForm(
        initial={
            'agreed_price': enquiry.property.sale_price,
            'buyer_name': enquiry.name,
        }
    )
    return render(
        request,
        'properties/lead_detail.html',
        {
            'enquiry': enquiry,
            'status_form': status_form,
            'visit_form': visit_form,
            'offer_form': offer_form,
            'deal_form': deal_form,
            'visits': enquiry.visits.select_related('property').all(),
            'offers': enquiry.offers.all(),
            'activities': enquiry.activities.select_related('actor').all()[:40],
            'deals': enquiry.sale_deals.all(),
        },
    )


@login_required
@privilege_required('manage_leads')
@require_POST
def lead_update(request, pk):
    enquiry = get_object_or_404(_leads_qs(request), pk=pk)
    brand = get_request_brand(request)
    form = LeadStatusForm(request.POST, instance=enquiry, users=users_for_brand(brand))
    if form.is_valid():
        old = enquiry.status
        form.save()
        if old != enquiry.status:
            log_lead_activity(
                enquiry,
                actor=request.user,
                verb='status_changed',
                message=f'{old} → {enquiry.status}',
            )
        log_activity(request=request, action='update', message=f'Lead {enquiry.pk} updated')
        messages.success(request, 'Lead updated.')
    else:
        messages.error(request, 'Could not update lead.')
    return redirect('lead_detail', pk=enquiry.pk)


@login_required
@privilege_required('manage_leads')
@require_POST
def lead_visit_add(request, pk):
    enquiry = get_object_or_404(_leads_qs(request), pk=pk)
    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    form = LeadVisitForm(request.POST, properties=props)
    if form.is_valid():
        visit = form.save(commit=False)
        visit.enquiry = enquiry
        visit.created_by = request.user
        visit.save()
        log_lead_activity(
            enquiry,
            actor=request.user,
            verb='visit',
            message=f'Visit {visit.get_status_display()} on {visit.scheduled_at}',
        )
        if enquiry.property.owner_id:
            notify_user(
                user=enquiry.property.owner,
                brand=brand,
                kind='visit',
                title=f'Visit scheduled: {enquiry.name}',
                url=reverse('lead_detail', args=[enquiry.pk]),
            )
        log_activity(request=request, action='create', message=f'Visit for lead {enquiry.pk}')
        messages.success(request, 'Visit saved.')
    else:
        messages.error(request, 'Could not save visit. Check the date and unit.')
    return redirect('lead_detail', pk=enquiry.pk)


@login_required
@privilege_required('manage_leads')
@require_POST
def lead_offer_add(request, pk):
    enquiry = get_object_or_404(_leads_qs(request), pk=pk)
    form = OfferForm(request.POST)
    if form.is_valid():
        offer = form.save(commit=False)
        offer.enquiry = enquiry
        offer.property = enquiry.property
        offer.created_by = request.user
        offer.save()
        log_lead_activity(
            enquiry,
            actor=request.user,
            verb='offer',
            message=f'{offer.get_offer_type_display()} offer ₹{offer.amount} ({offer.get_status_display()})',
        )
        if enquiry.property.owner_id:
            notify_user(
                user=enquiry.property.owner,
                brand=get_request_brand(request),
                kind='offer',
                title=f'Offer on {enquiry.property.title}',
                url=reverse('lead_detail', args=[enquiry.pk]),
            )
        log_activity(request=request, action='create', message=f'Offer for lead {enquiry.pk}')
        messages.success(request, 'Offer logged.')
    else:
        messages.error(request, 'Could not save offer.')
    return redirect('lead_detail', pk=enquiry.pk)


@login_required
@privilege_required('manage_leads')
@require_POST
def lead_convert_tenant(request, pk):
    enquiry = get_object_or_404(_leads_qs(request), pk=pk)
    prop = enquiry.property
    if not prop.is_for_rent:
        messages.error(request, 'Convert to tenant is only for rent listings.')
        return redirect('lead_detail', pk=enquiry.pk)
    if enquiry.converted_tenant_id:
        messages.info(request, 'This lead is already converted.')
        return redirect('lead_detail', pk=enquiry.pk)
    tenant = Tenant.objects.create(
        property=prop,
        name=enquiry.name,
        phone=enquiry.phone or '',
        email=enquiry.email,
        is_active=True,
        move_in_date=enquiry.preferred_move_in or timezone.localdate(),
        advance_paid=prop.advance_amount or 0,
        notes=f'Converted from lead #{enquiry.pk}',
    )
    enquiry.converted_tenant = tenant
    enquiry.status = 'converted'
    enquiry.is_read = True
    enquiry.save(update_fields=['converted_tenant', 'status', 'is_read'])
    prop.is_occupied = True
    prop.save(update_fields=['is_occupied'])
    log_lead_activity(enquiry, actor=request.user, verb='converted', message=f'Tenant {tenant.name}')
    messages.success(request, f'{tenant.name} added as tenant. Link a login from the tenant form if needed.')
    return redirect('tenant_edit', pk=prop.pk, tenant_id=tenant.pk)


@login_required
@privilege_required('manage_leads')
@require_POST
def lead_convert_deal(request, pk):
    enquiry = get_object_or_404(_leads_qs(request), pk=pk)
    prop = enquiry.property
    if not prop.is_for_sale:
        messages.error(request, 'Convert to deal is only for sale listings.')
        return redirect('lead_detail', pk=enquiry.pk)
    form = SaleDealForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Check the deal amounts and dates.')
        return redirect('lead_detail', pk=enquiry.pk)
    accepted = enquiry.offers.filter(status='accepted').first()
    deal = form.save(commit=False)
    deal.property = prop
    deal.enquiry = enquiry
    deal.offer = accepted
    deal.buyer_name = enquiry.name
    deal.buyer_phone = enquiry.phone or ''
    deal.buyer_email = enquiry.email
    deal.created_by = request.user
    deal.save()
    enquiry.converted_deal = deal
    enquiry.status = 'converted'
    enquiry.is_read = True
    enquiry.save(update_fields=['converted_deal', 'status', 'is_read'])
    log_lead_activity(
        enquiry,
        actor=request.user,
        verb='converted',
        message=f'Deal ₹{deal.agreed_price} ({deal.get_status_display()})',
    )
    log_activity(request=request, action='create', message=f'Sale deal {deal.pk}')
    messages.success(request, 'Sale deal created.')
    return redirect('lead_detail', pk=enquiry.pk)


@login_required
@privilege_required('manage_tenants')
def tenant_list(request):
    brand = get_request_brand(request)
    start = month_start()
    tenants = (
        Tenant.objects.filter(property__in=Property.for_user(request.user, brand=brand), brand=brand)
        .select_related('property', 'property__building', 'user')
        .order_by('-is_active', 'name')
    )
    rows = []
    for tenant in tenants:
        paid = tenant.payments.filter(
            month_for__year=start.year,
            month_for__month=start.month,
            status__in=['paid', 'partial'],
        ).exists()
        rent_status = 'Paid' if paid else ('Due' if tenant.is_active else '—')
        loc = tenant.property.unit_label
        rows.append(
            {
                'name': mark_safe(
                    f'<a href="{reverse("tenant_edit", args=[tenant.property_id, tenant.pk])}">{tenant.name}</a>'
                ),
                'unit': loc,
                'phone': tenant.phone or '—',
                'lease': tenant.lease_end_date.strftime('%d %b %Y') if tenant.lease_end_date else '—',
                'advance': f'₹{tenant.advance_balance:,.0f}',
                'rent': rent_status,
                'active': 'Active' if tenant.is_active else 'Past',
                'actions': mark_safe(
                    f'<a class="btn btn-secondary btn-sm" href="{reverse("tenant_edit", args=[tenant.property_id, tenant.pk])}">Edit</a> '
                    + (
                        f'<a class="btn btn-primary btn-sm" href="{reverse("tenant_create_login", args=[tenant.property_id, tenant.pk])}">Create login</a>'
                        if not tenant.user_id
                        else f'<span class="meta">{tenant.user.username}</span>'
                    )
                ),
            }
        )
    return render(
        request,
        'properties/tenants.html',
        {
            'page_header': build_page_header(
                'Tenants',
                subtitle='All tenants across your units this brand. Create login details here if the tenant is not in the system yet.',
            ),
            'table': build_table(
                id='tenants',
                columns=[
                    {'key': 'name', 'label': 'Name', 'html': True},
                    {'key': 'unit', 'label': 'Building / unit'},
                    {'key': 'phone', 'label': 'Phone'},
                    {'key': 'lease', 'label': 'Lease end'},
                    {'key': 'advance', 'label': 'Advance'},
                    {'key': 'rent', 'label': 'This month'},
                    {'key': 'active', 'label': 'Status', 'badge': True},
                    {'key': 'actions', 'label': '', 'html': True, 'width': '220px'},
                ],
                rows=rows,
                empty_text='No tenants yet.',
            ),
        },
    )


@login_required
@privilege_required('view_inbox')
def inbox(request):
    brand = get_request_brand(request)
    notes = UserNotification.objects.filter(user=request.user, brand=brand)
    unread = notes.filter(is_read=False).count()
    rows = []
    for note in notes[:80]:
        title = note.title
        if note.url:
            title = mark_safe(f'<a href="{note.url}">{note.title}</a>')
        rows.append(
            {
                'when': note.created_at.strftime('%d %b %Y %H:%M'),
                'kind': note.get_kind_display(),
                'title': title,
                'read': 'Read' if note.is_read else 'New',
            }
        )
    return render(
        request,
        'properties/inbox.html',
        {
            'page_header': build_page_header(
                'Inbox',
                subtitle='Rent due, leads, visits, complaints, and campaign tasks.',
                actions=[
                    build_button('Mark all read', href=reverse('inbox_mark_all'), variant='secondary'),
                ],
            ),
            'kpis': build_kpis(
                [
                    {'label': 'Unread', 'value': unread, 'tone': 'warn' if unread else 'ok'},
                    {'label': 'Total', 'value': notes.count()},
                ]
            ),
            'table': build_table(
                id='inbox',
                columns=[
                    {'key': 'when', 'label': 'When', 'width': '140px'},
                    {'key': 'kind', 'label': 'Type', 'badge': True},
                    {'key': 'title', 'label': 'Message', 'html': True},
                    {'key': 'read', 'label': 'Status'},
                ],
                rows=rows,
                empty_text='No notifications yet.',
            ),
        },
    )


@login_required
@privilege_required('view_inbox')
def inbox_mark_all(request):
    brand = get_request_brand(request)
    UserNotification.objects.filter(user=request.user, brand=brand, is_read=False).update(is_read=True)
    messages.success(request, 'Inbox marked read.')
    return redirect('inbox')


@login_required
@privilege_required('view_reports')
def reports_csv(request):
    brand = get_request_brand(request)
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month
    props = Property.for_user(request.user, brand=brand)
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['Property', 'Building', 'Income', 'Expenses', 'Net', 'Month', 'Year'])
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
        writer.writerow(
            [
                prop.title,
                prop.building.name if prop.building_id else '',
                str(p_income),
                str(p_expense),
                str(p_income - p_expense),
                month,
                year,
            ]
        )
    response = HttpResponse(buffer.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="reports-{year}-{month:02d}.csv"'
    return response


@login_required
@privilege_required('manage_documents')
def document_add(request, pk):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, brand=brand)
    if not prop.user_can_manage(request.user, brand=brand):
        return HttpResponseForbidden('Not allowed')
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, property_obj=prop)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.property = prop
            doc.building = prop.building
            doc.brand = brand
            doc.uploaded_by = request.user
            doc.save()
            messages.success(request, 'Document uploaded.')
            return redirect('property_manage', pk=prop.pk)
    else:
        form = DocumentForm(property_obj=prop)
    return render(
        request,
        'properties/document_form.html',
        {'form': form, 'property': prop},
    )


@login_required
@privilege_required('view_calendar')
def calendar_view(request):
    brand = get_request_brand(request)
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month
    props = Property.for_user(request.user, brand=brand)
    events = []
    start = date(year, month, 1)
    last = monthrange(year, month)[1]
    end = date(year, month, last)
    visits = LeadVisit.objects.filter(
        property__in=props,
        scheduled_at__date__gte=start,
        scheduled_at__date__lte=end,
    ).select_related('enquiry', 'property')
    for visit in visits:
        events.append(
            {
                'day': visit.scheduled_at.date().day,
                'label': f'Visit · {visit.enquiry.name}',
                'href': reverse('lead_detail', args=[visit.enquiry_id]),
            }
        )
    for tenant in Tenant.objects.filter(property__in=props, is_active=True, lease_end_date__range=(start, end)):
        events.append(
            {
                'day': tenant.lease_end_date.day,
                'label': f'Lease end · {tenant.name}',
                'href': reverse('tenant_edit', args=[tenant.property_id, tenant.pk]),
            }
        )
    for deal in SaleDeal.objects.filter(property__in=props, token_date__range=(start, end)):
        events.append(
            {
                'day': deal.token_date.day,
                'label': f'Token · {deal.buyer_name}',
                'href': reverse('lead_detail', args=[deal.enquiry_id]) if deal.enquiry_id else '#',
            }
        )
    by_day = {}
    for ev in events:
        by_day.setdefault(ev['day'], []).append(ev)
    weeks = []
    first_weekday = start.weekday()  # Mon=0
    day = 1
    week = [None] * first_weekday
    while day <= last:
        week.append({'day': day, 'events': by_day.get(day, []), 'today': date(year, month, day) == today})
        if len(week) == 7:
            weeks.append(week)
            week = []
        day += 1
    if week:
        while len(week) < 7:
            week.append(None)
        weeks.append(week)
    prev_month = (start - timedelta(days=1)).replace(day=1)
    next_month = (end + timedelta(days=1))
    return render(
        request,
        'properties/calendar.html',
        {
            'year': year,
            'month': month,
            'month_label': start.strftime('%B %Y'),
            'weeks': weeks,
            'prev': {'year': prev_month.year, 'month': prev_month.month},
            'next': {'year': next_month.year, 'month': next_month.month},
            'page_header': build_page_header(
                'Calendar',
                subtitle='Visits, lease ends, and sale token dates.',
            ),
        },
    )


@login_required
@privilege_required('send_messages')
def thread_view(request, pk):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, brand=brand)
    tenant = prop.tenants.filter(is_active=True).first()
    if tenant is None:
        messages.error(request, 'No active tenant to message.')
        return redirect('property_manage', pk=prop.pk)
    can_owner = prop.user_can_manage(request.user, brand=brand)
    can_tenant = tenant.user_id == request.user.id
    if not (can_owner or can_tenant):
        return HttpResponseForbidden('Not allowed')
    thread, _ = MessageThread.objects.get_or_create(
        brand=brand,
        property=prop,
        tenant=tenant,
    )
    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                thread=thread,
                sender=request.user,
                body=form.cleaned_data['body'],
            )
            other = tenant.user if can_owner else prop.owner
            notify_user(
                user=other,
                brand=brand,
                kind='message',
                title=f'New message on {prop.title}',
                url=reverse('thread_view', args=[prop.pk]),
            )
            messages.success(request, 'Message sent.')
            return redirect('thread_view', pk=prop.pk)
    else:
        form = MessageForm()
    thread.messages.exclude(sender=request.user).update(is_read=True)
    return render(
        request,
        'properties/messages.html',
        {
            'property': prop,
            'tenant': tenant,
            'thread': thread,
            'msgs': thread.messages.select_related('sender'),
            'form': form,
        },
    )


@login_required
@privilege_required('manage_meters')
def meter_add(request, pk):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, brand=brand)
    if not prop.user_can_manage(request.user, brand=brand):
        return HttpResponseForbidden('Not allowed')
    if request.method == 'POST':
        form = MeterReadingForm(request.POST, request.FILES)
        if form.is_valid():
            reading = form.save(commit=False)
            reading.property = prop
            reading.brand = brand
            reading.created_by = request.user
            reading.save()
            messages.success(request, 'Meter reading saved.')
            return redirect('property_manage', pk=prop.pk)
    else:
        form = MeterReadingForm(initial={'reading_date': timezone.localdate()})
    return render(
        request,
        'properties/meter_form.html',
        {'form': form, 'property': prop},
    )


@login_required
@privilege_required('pay_rent')
@require_POST
def tenant_pay(request, payment_id):
    brand = get_request_brand(request)
    payment = get_object_or_404(
        RentPayment,
        pk=payment_id,
        brand=brand,
        tenant__user=request.user,
        status__in=['pending', 'overdue', 'partial'],
    )
    amount = payment.amount + (payment.late_fee or 0)
    order = PaymentOrder.objects.create(
        brand=brand,
        rent_payment=payment,
        gateway='manual',
        gateway_order_id=uuid.uuid4().hex[:16],
        amount=amount,
        status='paid',
        raw_payload={'simulated': True},
    )
    payment.status = 'paid'
    payment.payment_date = timezone.localdate()
    payment.save(update_fields=['status', 'payment_date'])
    if payment.property.owner_id:
        notify_user(
            user=payment.property.owner,
            brand=brand,
            kind='rent_due',
            title=f'Rent paid for {payment.property.title}',
            url=reverse('payment_receipt', args=[payment.property_id, payment.pk]),
        )
    messages.success(request, f'Payment of ₹{amount:,.0f} recorded (order {order.gateway_order_id}).')
    return redirect('tenant_portal')


@login_required
@privilege_required('save_listings')
def saved_listings(request):
    brand = get_request_brand(request)
    saved = SavedListing.objects.filter(user=request.user, brand=brand).select_related(
        'property', 'property__building'
    )
    rows = []
    for item in saved:
        prop = item.property
        rows.append(
            {
                'title': mark_safe(
                    f'<a href="{reverse("public_detail", args=[prop.pk])}">{prop.title}</a>'
                ),
                'where': prop.unit_label or prop.city,
                'price': prop.display_price,
                'saved': item.created_at.strftime('%d %b %Y'),
            }
        )
    return render(
        request,
        'properties/saved.html',
        {
            'page_header': build_page_header('Saved listings', subtitle='Your shortlist for this brand.'),
            'table': build_table(
                id='saved',
                columns=[
                    {'key': 'title', 'label': 'Listing', 'html': True},
                    {'key': 'where', 'label': 'Location'},
                    {'key': 'price', 'label': 'Price'},
                    {'key': 'saved', 'label': 'Saved'},
                ],
                rows=rows,
                empty_text='No saved listings yet. Open a listing and tap Save.',
            ),
        },
    )


@login_required
@privilege_required('save_listings')
@require_POST
def saved_toggle(request, pk):
    brand = get_request_brand(request)
    prop = get_object_or_404(Property, pk=pk, brand=brand, is_listed_publicly=True)
    existing = SavedListing.objects.filter(user=request.user, property=prop, brand=brand).first()
    if existing:
        existing.delete()
        messages.success(request, 'Removed from saved listings.')
    else:
        SavedListing.objects.create(user=request.user, property=prop, brand=brand)
        messages.success(request, 'Saved to your shortlist.')
    return redirect('public_detail', pk=prop.pk)


@login_required
@privilege_required('view_commissions')
def commissions(request):
    brand = get_request_brand(request)
    props = Property.for_user(request.user, brand=brand)
    deals = SaleDeal.objects.filter(property__in=props, brand=brand).select_related('property')
    rows = []
    for deal in deals:
        if not deal.commission_amount:
            continue
        rows.append(
            {
                'who': deal.buyer_name,
                'property': deal.property.title,
                'amount': f'₹{deal.commission_amount:,.0f}',
                'status': deal.get_status_display(),
                'kind': 'Sale',
            }
        )
    payouts = CommissionPayout.objects.filter(brand=brand, property__in=props)
    for payout in payouts:
        rows.append(
            {
                'who': payout.user.username,
                'property': payout.property.title if payout.property_id else '—',
                'amount': f'₹{payout.amount:,.0f}',
                'status': payout.get_status_display(),
                'kind': 'Payout',
            }
        )
    return render(
        request,
        'properties/commissions.html',
        {
            'page_header': build_page_header(
                'Commissions',
                subtitle='Sale deal commission and recorded payouts.',
            ),
            'table': build_table(
                id='commissions',
                columns=[
                    {'key': 'kind', 'label': 'Kind'},
                    {'key': 'who', 'label': 'Party'},
                    {'key': 'property', 'label': 'Property'},
                    {'key': 'amount', 'label': 'Amount'},
                    {'key': 'status', 'label': 'Status'},
                ],
                rows=rows,
                empty_text='No commissions yet.',
            ),
        },
    )
