"""Shared Django Unfold admin mixins for PropKeep."""

from __future__ import annotations

import csv
from datetime import date, timedelta

from django.contrib import admin, messages
from django.db.models import ForeignKey
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .brand_scoping import assign_brand, filter_by_brand, get_request_brand, users_for_brand
from .logging_utils import log_activity
from .models import Brand


class BrandScopedModelAdmin(ModelAdmin):
    """Scope changelists and FK choices to the active brand."""

    brand_path = None
    warn_unsaved_form = True
    list_filter_submit = True
    change_form_show_cancel_button = True

    def get_active_brand(self, request):
        return get_request_brand(request)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        brand = self.get_active_brand(request)
        if brand is None:
            return qs.none()
        if hasattr(qs.model, 'brand_id'):
            return qs.filter(brand=brand)
        if self.brand_path:
            return qs.filter(**{self.brand_path: brand})
        return qs

    def save_model(self, request, obj, form, change):
        if not change and hasattr(obj, 'brand_id') and not obj.brand_id:
            assign_brand(obj, self.get_active_brand(request))
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        brand = self.get_active_brand(request)
        if brand is not None:
            if db_field.name == 'brand':
                kwargs['queryset'] = Brand.objects.filter(is_active=True)
            elif db_field.name == 'user':
                kwargs['queryset'] = users_for_brand(brand)
            elif isinstance(db_field, ForeignKey):
                related = db_field.remote_field.model
                if hasattr(related, 'brand_id'):
                    kwargs['queryset'] = filter_by_brand(related.objects.all(), brand)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


class CsvExportMixin:
    """Add a CSV export list action."""

    csv_export_fields = None
    csv_export_filename = 'export.csv'

    @admin.action(description=_('Export selected to CSV'))
    def export_selected_csv(self, request, queryset):
        fields = self.csv_export_fields or [
            f.name for f in self.model._meta.fields if f.name != 'id'
        ]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.csv_export_filename}"'
        writer = csv.writer(response)
        writer.writerow(fields)
        for obj in queryset:
            row = []
            for name in fields:
                value = getattr(obj, name, '')
                if hasattr(value, 'pk'):
                    value = str(value)
                row.append(value)
            writer.writerow(row)
        log_activity(
            request=request,
            action='export',
            message=f'CSV export: {self.model._meta.label} ({queryset.count()} rows)',
        )
        return response


class AdminAuditMixin:
    """Log sensitive admin mutations to ActivityLog."""

    audit_log_fields = None

    def _audit(self, request, action, message):
        log_activity(request=request, action=action, message=message[:500])

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        verb = 'update' if change else 'create'
        self._audit(request, verb, f'{obj._meta.label}: {obj}')


class PaidInvoiceGuardMixin:
    """Lock financial fields on paid invoices unless user can change them."""

    paid_invoice_readonly = (
        'amount',
        'late_fee',
        'status',
        'month_for',
        'due_date',
        'payment_date',
        'property',
        'tenant',
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and getattr(obj, 'status', None) == 'paid':
            if not self.has_change_permission(request, obj):
                readonly.extend(self.paid_invoice_readonly)
            elif request.user.groups.filter(name='Finance viewer').exists() and not request.user.is_superuser:
                readonly.extend(self.paid_invoice_readonly)
        return tuple(dict.fromkeys(readonly))


class PastTenantGuardMixin:
    """Past customers stay readonly except notes and contact tweaks."""

    past_tenant_readonly = (
        'property',
        'move_in_date',
        'lease_end_date',
        'advance_paid',
        'advance_deduction',
        'advance_refunded',
        'user',
        'is_active',
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and not obj.is_active:
            readonly.extend(self.past_tenant_readonly)
        return tuple(dict.fromkeys(readonly))


def days_since(created_at):
    if not created_at:
        return 0
    return max(0, (timezone.now() - created_at).days)


def lease_days_remaining(obj):
    if not obj.lease_end_date:
        return None
    return (obj.lease_end_date - date.today()).days


def next_invoice_month_for(tenant):
    from properties.models import RentPayment

    last = (
        RentPayment.objects.filter(tenant=tenant)
        .order_by('-month_for')
        .values_list('month_for', flat=True)
        .first()
    )
    base = last or tenant.move_in_date or date.today()
    if base.month == 12:
        return date(base.year + 1, 1, 1)
    return date(base.year, base.month + 1, 1)
