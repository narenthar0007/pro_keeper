"""Unfold admin dashboard KPIs and environment callbacks.

Tenant is the customer record. RentPayment is the rent invoice.
"""

from datetime import date

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .brand_scoping import filter_by_brand, get_request_brand


def _shift_month(base: date, delta: int) -> date:
    year, month = base.year, base.month + delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return date(year, month, 1)


def _brand_qs(model, request):
    return filter_by_brand(model.objects.all(), get_request_brand(request))


def environment_callback(request):
    brand = get_request_brand(request)
    prefix = brand.name if brand else 'PropKeep'
    if settings.DEBUG:
        return [f'{prefix} · Development', 'warning']
    return [f'{prefix} · Production', 'danger']


def pending_invoices_badge(request):
    if not request.user.is_staff:
        return None
    from properties.models import RentPayment

    count = _brand_qs(RentPayment, request).filter(status__in=['pending', 'overdue']).count()
    return count or None


def unread_leads_badge(request):
    if not request.user.is_staff:
        return None
    from properties.models import Enquiry

    count = _brand_qs(Enquiry, request).filter(is_read=False).count()
    return count or None


def open_complaints_badge(request):
    if not request.user.is_staff:
        return None
    from properties.models import Complaint

    count = _brand_qs(Complaint, request).filter(status__in=['open', 'in_progress']).count()
    return count or None


def dashboard_callback(request, context):
    """Inject KPI cards, rent chart, and overdue table for templates/admin/index.html."""
    if not getattr(request.user, 'is_staff', False):
        return context

    from properties.models import Building, Complaint, Enquiry, Property, RentPayment, Tenant

    brand = get_request_brand(request)
    properties = _brand_qs(Property, request)
    tenants = _brand_qs(Tenant, request)
    payments = _brand_qs(RentPayment, request)
    enquiries = _brand_qs(Enquiry, request)
    buildings = _brand_qs(Building, request)

    properties_count = properties.count()
    occupied = properties.filter(is_occupied=True, listing_type='rent').count()
    tenants_count = tenants.filter(is_active=True).count()
    overdue_qs = payments.filter(status='overdue').select_related('tenant', 'property')
    overdue = overdue_qs.count()
    pending = payments.filter(status='pending').count()
    open_leads = enquiries.exclude(status='converted').count()
    buildings_count = buildings.filter(is_active=True).count()
    open_complaints = _brand_qs(Complaint, request).filter(status__in=['open', 'in_progress']).count()

    today = timezone.localdate()
    chart_rows = []
    anchor = today.replace(day=1)
    for i in range(5, -1, -1):
        month_start = _shift_month(anchor, -i)
        month_payments = payments.filter(
            month_for__year=month_start.year,
            month_for__month=month_start.month,
        )
        collected = sum(p.amount for p in month_payments.filter(status='paid'))
        due = sum(p.amount + p.late_fee for p in month_payments.exclude(status='paid'))
        chart_rows.append(
            {
                'label': month_start.strftime('%b %Y'),
                'collected': float(collected),
                'due': float(due),
            }
        )
    chart_max = max([max(r['collected'], r['due']) for r in chart_rows] + [1])

    overdue_rows = []
    for payment in overdue_qs.order_by('due_date', '-month_for')[:8]:
        days = 0
        if payment.due_date:
            days = max(0, (today - payment.due_date).days)
        overdue_rows.append(
            {
                'tenant': payment.tenant.name if payment.tenant_id else '—',
                'property': payment.property.title,
                'amount': payment.amount + payment.late_fee,
                'days': days,
                'url': reverse('admin:properties_rentpayment_change', args=[payment.pk]),
            }
        )

    context.update(
        {
            'dashboard_kpis': [
                {
                    'label': 'Listings',
                    'value': properties_count,
                    'hint': f'{occupied} occupied rent units',
                    'icon': 'home_work',
                    'link': reverse('admin:properties_property_changelist'),
                },
                {
                    'label': 'Customers',
                    'value': tenants_count,
                    'hint': 'Active tenant records',
                    'icon': 'group',
                    'link': reverse('admin:properties_tenant_changelist'),
                },
                {
                    'label': 'Invoices due',
                    'value': pending + overdue,
                    'hint': f'{overdue} overdue · {pending} pending',
                    'icon': 'receipt_long',
                    'link': reverse('admin:properties_rentpayment_changelist'),
                },
                {
                    'label': 'Open leads',
                    'value': open_leads,
                    'hint': f'{buildings_count} buildings · {open_complaints} complaints',
                    'icon': 'handshake',
                    'link': reverse('admin:properties_enquiry_changelist'),
                },
            ],
            'dashboard_rent_chart': chart_rows,
            'dashboard_chart_max': chart_max,
            'dashboard_overdue_rows': overdue_rows,
            'dashboard_brand_name': brand.name if brand else '',
        }
    )
    return context
