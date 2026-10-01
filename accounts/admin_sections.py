"""Unfold changelist row sections."""

from django.utils.translation import gettext_lazy as _
from unfold.sections import TableSection


class TenantPaymentsSection(TableSection):
    verbose_name = _('Recent invoices')
    related_name = 'payments'
    fields = ['month_for', 'amount', 'status', 'payment_date']
    height = 220


class PropertyTenantsSection(TableSection):
    verbose_name = _('Customers on this unit')
    related_name = 'tenants'
    fields = ['name', 'phone', 'is_active', 'move_in_date']
    height = 200


class PropertyPaymentsSection(TableSection):
    verbose_name = _('Recent rent invoices')
    related_name = 'payments'
    fields = ['tenant', 'month_for', 'amount', 'status']
    height = 220


class EnquiryVisitsSection(TableSection):
    verbose_name = _('Visits')
    related_name = 'visits'
    fields = ['scheduled_at', 'status', 'notes']
    height = 180
