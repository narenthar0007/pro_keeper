"""Unfold ModelAdmin for PropKeep.

Customer analog: Tenant
Invoice analog: RentPayment
"""

from datetime import date

from django.contrib import admin, messages
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import TabularInline
from unfold.contrib.filters.admin import (
    BooleanRadioFilter,
    ChoicesDropdownFilter,
    RangeDateFilter,
    RangeNumericFilter,
    RelatedDropdownFilter,
)
from unfold.decorators import action, display
from unfold.enums import ActionVariant

from accounts.admin_mixins import (
    AdminAuditMixin,
    BrandScopedModelAdmin,
    CsvExportMixin,
    PaidInvoiceGuardMixin,
    PastTenantGuardMixin,
    days_since,
    lease_days_remaining,
    next_invoice_month_for,
)
from accounts.admin_sections import (
    EnquiryVisitsSection,
    PropertyPaymentsSection,
    PropertyTenantsSection,
    TenantPaymentsSection,
)
from accounts.logging_utils import log_activity

from .campaign_jobs import run_jobs_for_campaign
from .models import (
    Amenity,
    Building,
    CampaignCollaborator,
    Complaint,
    Enquiry,
    Expense,
    LeadVisit,
    MarketingCampaign,
    Offer,
    Property,
    PropertyImage,
    PropertyShare,
    RentPayment,
    SaleDeal,
    SitePromotion,
    Tenant,
)


class UnfoldModelAdmin(BrandScopedModelAdmin):
    pass


class PropertyImageInline(TabularInline):
    model = PropertyImage
    extra = 0
    fields = ('image', 'caption', 'is_cover')
    tab = True


class TenantInline(TabularInline):
    model = Tenant
    extra = 0
    fields = ('name', 'phone', 'email', 'is_active', 'move_in_date')
    show_change_link = True
    tab = True


class RentPaymentInline(TabularInline):
    model = RentPayment
    extra = 0
    fields = ('tenant', 'month_for', 'amount', 'status', 'payment_date')
    show_change_link = True
    tab = True
    autocomplete_fields = ('tenant',)


@admin.register(Amenity)
class AmenityAdmin(BrandScopedModelAdmin):
    list_display = ('code', 'label')
    search_fields = ('code', 'label')
    list_filter_submit = False


@admin.register(Building)
class BuildingAdmin(UnfoldModelAdmin):
    list_display = ('name', 'city', 'owner', 'photo_thumb', 'is_active')
    list_filter = (
        ('is_active', BooleanRadioFilter),
        'city',
    )
    search_fields = ('name', 'address', 'city', 'owner__username')
    search_help_text = 'Search building name, address, city, or owner.'
    autocomplete_fields = ('owner', 'brand')
    readonly_fields = ('photo_preview',)

    @display(description=_('Photo'))
    def photo_thumb(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img src="{}" style="height:40px;border-radius:6px"/>', obj.photo.url)

    @display(description=_('Photo preview'))
    def photo_preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html('<img src="{}" style="max-height:120px;border-radius:8px"/>', obj.photo.url)


@admin.register(Property)
class PropertyAdmin(UnfoldModelAdmin):
    list_display = (
        'title',
        'listing_type',
        'city',
        'building',
        'occupancy_badge',
        'monthly_rent',
        'is_listed_publicly',
    )
    list_filter = (
        ('listing_type', ChoicesDropdownFilter),
        ('sale_status', ChoicesDropdownFilter),
        ('property_type', ChoicesDropdownFilter),
        ('building', RelatedDropdownFilter),
        ('is_occupied', BooleanRadioFilter),
        ('is_listed_publicly', BooleanRadioFilter),
        'city',
    )
    search_fields = ('title', 'address', 'city', 'owner__username', 'unit_number')
    search_help_text = 'Search title, address, city, unit, or owner username.'
    autocomplete_fields = ('owner', 'building', 'brand')
    inlines = [PropertyImageInline, TenantInline, RentPaymentInline]
    list_sections = [PropertyTenantsSection, PropertyPaymentsSection]
    list_sections_classes = 'lg:grid-cols-2'
    fieldsets = (
        (_('Listing'), {'fields': ('title', 'description', 'listing_type', 'property_type')}),
        (_('Building & unit'), {'fields': ('building', 'unit_number', 'floor_number', 'door_number')}),
        (
            _('Address'),
            {
                'fields': (
                    'street', 'landmark', 'address', 'city', 'state', 'pincode', 'country',
                    'latitude', 'longitude',
                ),
                'classes': ('collapse',),
            },
        ),
        (
            _('Commercial'),
            {
                'fields': (
                    'monthly_rent', 'advance_amount', 'sale_price', 'sale_status',
                    'price_negotiable', 'furnishing',
                )
            },
        ),
        (
            _('Visibility'),
            {
                'fields': (
                    'is_listed_publicly', 'is_occupied', 'allow_tenant_marketing',
                    'contact_phone', 'owner', 'brand', 'featured_image',
                )
            },
        ),
        (
            _('Details'),
            {
                'classes': ('collapse',),
                'fields': (
                    'bedrooms', 'bathrooms', 'area_sqft', 'year_of_building',
                    'possession_date', 'amenities', 'late_fee_amount', 'late_fee_grace_days',
                ),
            },
        ),
    )

    @display(
        description=_('Occupancy'),
        ordering='is_occupied',
        label={True: 'success', False: 'warning'},
    )
    def occupancy_badge(self, obj):
        return (obj.is_occupied, _('Occupied') if obj.is_occupied else _('Vacant'))


@admin.register(Tenant)
class TenantAdmin(PastTenantGuardMixin, CsvExportMixin, AdminAuditMixin, UnfoldModelAdmin):
    list_display = (
        'customer_identity',
        'property',
        'phone',
        'status_badge',
        'lease_remaining',
        'advance_balance_display',
        'move_in_date',
    )
    list_filter = (
        ('is_active', BooleanRadioFilter),
        ('property', RelatedDropdownFilter),
        ('move_in_date', RangeDateFilter),
    )
    search_fields = ('name', 'email', 'phone', 'property__title', 'user__username')
    search_help_text = 'Search customer name, email, phone, login, or listing title.'
    autocomplete_fields = ('property', 'user', 'brand')
    date_hierarchy = 'move_in_date'
    actions = ['export_selected_csv']
    actions_detail = ['end_lease', 'generate_next_invoice']
    list_sections = [TenantPaymentsSection]
    csv_export_filename = 'customers.csv'
    csv_export_fields = (
        'name', 'email', 'phone', 'property', 'is_active',
        'move_in_date', 'lease_end_date', 'advance_paid',
    )
    readonly_fields = ('lease_document_link',)
    fieldsets = (
        (_('Customer'), {'fields': ('name', 'phone', 'email', 'user', 'is_active')}),
        (_('Unit'), {'fields': ('property', 'brand')}),
        (_('Lease'), {'fields': ('move_in_date', 'lease_end_date', 'lease_document', 'lease_document_link', 'photo', 'notes')}),
        (
            _('Advance / deposit'),
            {'fields': ('advance_paid', 'advance_deduction', 'advance_refunded'), 'classes': ('collapse',)},
        ),
    )

    @display(description=_('Customer'), header=True)
    def customer_identity(self, obj):
        return obj.name, obj.email or obj.phone or 'No contact'

    @display(description=_('Status'), ordering='is_active', label={True: 'success', False: 'danger'})
    def status_badge(self, obj):
        return (obj.is_active, _('Active') if obj.is_active else _('Past'))

    @display(description=_('Lease left'))
    def lease_remaining(self, obj):
        remaining = lease_days_remaining(obj)
        if remaining is None:
            return '—'
        if remaining < 0:
            return _('Expired %sd ago') % abs(remaining)
        return _('%sd left') % remaining

    @display(description=_('Advance balance'), ordering='advance_paid')
    def advance_balance_display(self, obj):
        return obj.advance_balance

    @display(description=_('Lease document'))
    def lease_document_link(self, obj):
        if not obj.lease_document:
            return '—'
        return format_html(
            '<a class="text-primary-600 underline" href="{}" target="_blank" rel="noopener">Open lease file</a>',
            obj.lease_document.url,
        )

    @action(
        description=_('End this lease'),
        icon='event_busy',
        variant=ActionVariant.DANGER,
        permissions=['change'],
        dialog={
            'title': _('End lease'),
            'description': _('Set this customer to past. Occupancy is not auto-updated.'),
            'form_submit_text': _('End lease'),
        },
    )
    def end_lease(self, request, form, object_id):
        tenant = self.get_object(request, object_id)
        if tenant is None or not self.has_change_permission(request, tenant):
            messages.error(request, _('Not allowed.'))
        else:
            tenant.is_active = False
            tenant.save(update_fields=['is_active'])
            log_activity(request=request, action='update', message=f'Lease ended: {tenant.name}')
            messages.success(request, _('Lease ended for %s.') % tenant.name)
        return HttpResponse(headers={'HX-Redirect': reverse('admin:properties_tenant_changelist')})

    @action(
        description=_('Create next month invoice'),
        icon='receipt_long',
        variant=ActionVariant.SUCCESS,
        permissions=['add'],
        dialog={
            'title': _('Generate rent invoice'),
            'description': _('Creates a pending invoice for the next billing month.'),
            'form_submit_text': _('Generate invoice'),
        },
    )
    def generate_next_invoice(self, request, form, object_id):
        tenant = self.get_object(request, object_id)
        if tenant is None or not tenant.property_id:
            messages.error(request, _('Customer must be linked to a unit.'))
        elif not self.has_add_permission(request):
            messages.error(request, _('Not allowed.'))
        else:
            month_for = next_invoice_month_for(tenant)
            due_day = min(getattr(getattr(tenant.user, 'profile', None), 'rent_due_day', 5) or 5, 28)
            due_date = month_for.replace(day=due_day)
            amount = tenant.property.monthly_rent or 0
            payment, created = RentPayment.objects.get_or_create(
                tenant=tenant,
                property=tenant.property,
                month_for=month_for,
                defaults={
                    'amount': amount,
                    'status': 'pending',
                    'payment_date': due_date,
                    'due_date': due_date,
                    'brand': tenant.brand,
                },
            )
            if created:
                log_activity(request=request, action='create', message=f'Invoice generated: {tenant.name} {month_for:%b %Y}')
                messages.success(request, _('Invoice created for %s.') % month_for.strftime('%b %Y'))
            else:
                messages.warning(request, _('Invoice already exists for %s.') % month_for.strftime('%b %Y'))
        return HttpResponse(headers={'HX-Redirect': reverse('admin:properties_tenant_change', args=[object_id])})


@admin.register(RentPayment)
class RentPaymentAdmin(
    PaidInvoiceGuardMixin,
    CsvExportMixin,
    AdminAuditMixin,
    UnfoldModelAdmin,
):
    list_display = (
        'invoice_ref',
        'property',
        'tenant',
        'total_due',
        'month_for',
        'status_badge',
        'days_overdue',
        'payment_date',
    )
    list_filter = (
        ('status', ChoicesDropdownFilter),
        ('property', RelatedDropdownFilter),
        ('tenant', RelatedDropdownFilter),
        ('payment_date', RangeDateFilter),
        ('month_for', RangeDateFilter),
        ('amount', RangeNumericFilter),
    )
    search_fields = ('property__title', 'tenant__name', 'tenant__email', 'notes')
    search_help_text = 'Search listing, customer, email, or invoice notes.'
    autocomplete_fields = ('property', 'tenant', 'brand')
    date_hierarchy = 'month_for'
    actions = ['mark_selected_paid', 'export_selected_csv']
    actions_list = ['mark_overdue_paid', 'send_rent_reminders']
    actions_row = ['row_mark_paid']
    actions_detail = ['detail_mark_paid']
    csv_export_filename = 'invoices.csv'
    csv_export_fields = (
        'property', 'tenant', 'amount', 'late_fee', 'status',
        'month_for', 'due_date', 'payment_date', 'notes',
    )
    fieldsets = (
        (_('Invoice'), {'fields': ('property', 'tenant', 'brand')}),
        (_('Amount'), {'fields': ('amount', 'late_fee', 'status', 'month_for', 'due_date', 'payment_date')}),
        (_('Notes'), {'fields': ('notes',), 'classes': ('collapse',)}),
    )

    def has_change_permission(self, request, obj=None):
        if request.user.groups.filter(name='Finance viewer').exists() and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        if request.user.groups.filter(name='Finance viewer').exists() and not request.user.is_superuser:
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        if request.user.groups.filter(name='Finance viewer').exists() and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)

    @display(description=_('Invoice'), header=True)
    def invoice_ref(self, obj):
        month = obj.month_for.strftime('%b %Y') if obj.month_for else '—'
        who = obj.tenant.name if obj.tenant_id else 'Unassigned'
        return month, who

    @display(description=_('Total'), ordering='amount')
    def total_due(self, obj):
        return obj.amount + obj.late_fee

    @display(
        description=_('Status'),
        ordering='status',
        label={'paid': 'success', 'pending': 'warning', 'partial': 'info', 'overdue': 'danger'},
    )
    def status_badge(self, obj):
        return obj.status, obj.get_status_display()

    @display(description=_('Overdue'))
    def days_overdue(self, obj):
        if obj.status not in ('overdue', 'pending') or not obj.due_date:
            return '—'
        days = max(0, (date.today() - obj.due_date).days)
        return f'{days}d' if days else '—'

    @admin.action(description=_('Mark selected invoices as paid'))
    def mark_selected_paid(self, request, queryset):
        if not self.has_change_permission(request):
            messages.error(request, _('Not allowed.'))
            return
        updated = queryset.update(status='paid')
        log_activity(request=request, action='update', message=f'Marked {updated} invoices paid')
        self.message_user(request, _('%s invoices marked paid.') % updated)

    def _mark_paid(self, request, payment):
        if payment is None or not self.has_change_permission(request, payment):
            messages.error(request, _('Not allowed.'))
            return
        payment.status = 'paid'
        payment.save(update_fields=['status'])
        log_activity(request=request, action='update', message=f'Invoice paid: {payment}')
        messages.success(request, _('Invoice marked paid.'))

    @action(
        description=_('Mark overdue invoices paid'),
        icon='done_all',
        variant=ActionVariant.SUCCESS,
        permissions=['change'],
        dialog={
            'title': _('Collect overdue invoices'),
            'description': _('Set every overdue rent invoice in this brand to paid.'),
            'form_submit_text': _('Mark overdue paid'),
        },
    )
    def mark_overdue_paid(self, request, form):
        if not self.has_change_permission(request):
            messages.error(request, _('Not allowed.'))
        else:
            updated = self.get_queryset(request).filter(status='overdue').update(status='paid')
            log_activity(request=request, action='update', message=f'Bulk overdue paid: {updated}')
            messages.success(request, _('%s overdue invoices marked paid.') % updated)
        return HttpResponse(headers={'HX-Redirect': reverse('admin:properties_rentpayment_changelist')})

    @action(
        description=_('Log rent reminders'),
        icon='notifications',
        permissions=['view'],
        dialog={
            'title': _('Rent reminder batch'),
            'description': _('Logs a reminder entry for each pending/overdue invoice (email sending uses owner settings).'),
            'form_submit_text': _('Log reminders'),
        },
    )
    def send_rent_reminders(self, request, form):
        qs = self.get_queryset(request).filter(status__in=['pending', 'overdue']).select_related('tenant', 'property')
        count = qs.count()
        log_activity(request=request, action='other', message=f'Rent reminders logged for {count} invoices')
        messages.success(request, _('Reminder batch logged for %s invoices.') % count)
        return HttpResponse(headers={'HX-Redirect': reverse('admin:properties_rentpayment_changelist')})

    @action(description=_('Mark paid'), icon='check_circle', variant=ActionVariant.SUCCESS, permissions=['change'],
            dialog={'title': _('Mark invoice paid'), 'description': _('Confirm collection.'), 'form_submit_text': _('Mark paid')})
    def row_mark_paid(self, request, form, object_id):
        self._mark_paid(request, self.get_object(request, object_id))
        return HttpResponse(headers={'HX-Redirect': reverse('admin:properties_rentpayment_changelist')})

    @action(description=_('Mark paid'), icon='check_circle', variant=ActionVariant.SUCCESS, permissions=['change'],
            dialog={'title': _('Mark invoice paid'), 'description': _('Confirm collection.'), 'form_submit_text': _('Mark paid')})
    def detail_mark_paid(self, request, form, object_id):
        payment = self.get_object(request, object_id)
        self._mark_paid(request, payment)
        return HttpResponse(headers={'HX-Redirect': reverse('admin:properties_rentpayment_change', args=[object_id])})


@admin.register(Expense)
class ExpenseAdmin(CsvExportMixin, UnfoldModelAdmin):
    list_display = ('title', 'property', 'category', 'amount', 'expense_date')
    list_filter = (
        ('category', ChoicesDropdownFilter),
        ('property', RelatedDropdownFilter),
        ('expense_date', RangeDateFilter),
    )
    search_fields = ('title', 'property__title', 'notes')
    search_help_text = 'Search expense title, listing, or notes.'
    autocomplete_fields = ('property', 'brand')
    actions = ['export_selected_csv']
    csv_export_filename = 'expenses.csv'


@admin.register(Enquiry)
class EnquiryAdmin(AdminAuditMixin, UnfoldModelAdmin):
    list_display = ('name', 'property', 'lead_status', 'lead_age', 'assigned_to', 'is_read', 'created_at')
    list_filter = (
        ('status', ChoicesDropdownFilter),
        ('enquiry_type', ChoicesDropdownFilter),
        ('is_read', BooleanRadioFilter),
        ('property', RelatedDropdownFilter),
    )
    search_fields = ('name', 'email', 'phone', 'property__title', 'message')
    search_help_text = 'Search lead name, contact, listing, or message text.'
    autocomplete_fields = ('property', 'assigned_to', 'brand', 'campaign')
    actions_detail = ['convert_to_tenant']
    list_sections = [EnquiryVisitsSection]

    @display(description=_('Status'), ordering='status', label=True)
    def lead_status(self, obj):
        return obj.get_status_display()

    @display(description=_('Age'))
    def lead_age(self, obj):
        return _('%sd') % days_since(obj.created_at)

    @action(
        description=_('Convert to customer'),
        icon='person_add',
        variant=ActionVariant.SUCCESS,
        permissions=['add', 'change'],
        dialog={
            'title': _('Convert lead to customer'),
            'description': _('Creates an active tenant from this lead and marks the lead converted.'),
            'form_submit_text': _('Convert'),
        },
    )
    def convert_to_tenant(self, request, form, object_id):
        enquiry = self.get_object(request, object_id)
        if enquiry is None or enquiry.enquiry_type == 'buy':
            messages.error(request, _('Only rent leads can convert to tenants.'))
        elif enquiry.converted_tenant_id:
            messages.warning(request, _('Lead already converted.'))
        elif not self.has_add_permission(request):
            messages.error(request, _('Not allowed.'))
        else:
            tenant = Tenant.objects.create(
                property=enquiry.property,
                brand=enquiry.brand,
                name=enquiry.name,
                email=enquiry.email,
                phone=enquiry.phone,
                move_in_date=enquiry.preferred_move_in,
                is_active=True,
            )
            enquiry.status = 'converted'
            enquiry.converted_tenant = tenant
            enquiry.is_read = True
            enquiry.save(update_fields=['status', 'converted_tenant', 'is_read'])
            log_activity(request=request, action='create', message=f'Lead converted: {enquiry.name} → tenant #{tenant.pk}')
            messages.success(request, _('Customer %s created.') % tenant.name)
        return HttpResponse(headers={'HX-Redirect': reverse('admin:properties_enquiry_changelist')})


@admin.register(LeadVisit)
class LeadVisitAdmin(UnfoldModelAdmin):
    list_display = ('enquiry', 'property', 'scheduled_at', 'status')
    list_filter = (('status', ChoicesDropdownFilter), ('scheduled_at', RangeDateFilter))
    search_fields = ('enquiry__name', 'property__title', 'notes')
    autocomplete_fields = ('enquiry', 'property', 'created_by')


@admin.register(Offer)
class OfferAdmin(UnfoldModelAdmin):
    list_display = ('enquiry', 'offer_type', 'amount', 'status')
    list_filter = (('status', ChoicesDropdownFilter),)
    search_fields = ('enquiry__name',)
    autocomplete_fields = ('enquiry',)


@admin.register(SaleDeal)
class SaleDealAdmin(UnfoldModelAdmin):
    list_display = ('property', 'buyer_name', 'agreed_price', 'status')
    list_filter = (('status', ChoicesDropdownFilter),)
    search_fields = ('buyer_name', 'property__title')
    autocomplete_fields = ('property', 'enquiry')


@admin.register(Complaint)
class ComplaintAdmin(UnfoldModelAdmin):
    list_display = ('title', 'property', 'tenant', 'status', 'sla_badge', 'created_at')
    list_filter = (
        ('status', ChoicesDropdownFilter),
        ('priority', ChoicesDropdownFilter),
        ('property', RelatedDropdownFilter),
    )
    search_fields = ('title', 'property__title', 'tenant__name', 'description')
    search_help_text = 'Search complaint title, listing, tenant, or description.'
    autocomplete_fields = ('property', 'tenant', 'building', 'created_by')
    readonly_fields = ('photo_preview',)

    @display(
        description=_('SLA'),
        label={'ok': 'success', 'warn': 'warning', 'bad': 'danger'},
    )
    def sla_badge(self, obj):
        if obj.status in ('resolved', 'closed'):
            return ('ok', _('Closed'))
        age = days_since(obj.created_at)
        if age > 7:
            return ('bad', _('%sd open') % age)
        if age > 3:
            return ('warn', _('%sd open') % age)
        return ('ok', _('%sd open') % age)

    @display(description=_('Photo'))
    def photo_preview(self, obj):
        if not obj.photo:
            return '—'
        return format_html(
            '<a href="{}" target="_blank" rel="noopener"><img src="{}" alt="" style="max-height:120px;border-radius:8px"/></a>',
            obj.photo.url,
            obj.photo.url,
        )


@admin.register(PropertyShare)
class PropertyShareAdmin(UnfoldModelAdmin):
    brand_path = 'property__brand'
    list_display = ('property', 'user', 'role', 'created_at')
    search_fields = ('property__title', 'user__username')
    autocomplete_fields = ('property', 'user')


@admin.register(PropertyImage)
class PropertyImageAdmin(UnfoldModelAdmin):
    brand_path = 'property__brand'
    list_display = ('property', 'caption', 'is_cover', 'thumb', 'uploaded_at')
    search_fields = ('property__title', 'caption')
    autocomplete_fields = ('property',)
    readonly_fields = ('thumb',)

    @display(description=_('Preview'))
    def thumb(self, obj):
        if not obj.image:
            return '—'
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" style="max-height:64px;border-radius:6px"/></a>',
            obj.image.url,
            obj.image.url,
        )


@admin.register(MarketingCampaign)
class MarketingCampaignAdmin(AdminAuditMixin, UnfoldModelAdmin):
    list_display = ('title', 'property', 'channel', 'status', 'content_today', 'budget', 'leads_count')
    list_filter = (
        ('status', ChoicesDropdownFilter),
        ('channel', ChoicesDropdownFilter),
    )
    search_fields = ('title', 'property__title', 'notes')
    search_help_text = 'Search campaign title, listing, or notes.'
    autocomplete_fields = ('property', 'created_by', 'brand')
    actions_detail = ['run_campaign_now']
    readonly_fields = ('job_status_display',)

    @display(description=_('Today content'))
    def content_today(self, obj):
        done = obj.content_done_for_date(timezone.localdate())
        return f'{done["photos"]}/{obj.photos_per_day} photos · {done["videos"]}/{obj.videos_per_day} videos'

    @display(description=_('Job status'))
    def job_status_display(self, obj):
        if obj.status != 'active':
            return obj.get_status_display()
        today = timezone.localdate()
        done = obj.content_done_for_date(today)
        if obj.should_auto_complete(today=today):
            return _('Ready to auto-complete')
        if done['photos'] >= obj.photos_per_day and done['videos'] >= obj.videos_per_day:
            return _('On track today')
        return _('Content missing today')

    @action(
        description=_('Run campaign jobs now'),
        icon='play_circle',
        permissions=['change'],
        dialog={
            'title': _('Run jobs for this campaign'),
            'description': _('Send content reminders and auto-complete if eligible.'),
            'form_submit_text': _('Run now'),
        },
    )
    def run_campaign_now(self, request, form, object_id):
        campaign = self.get_object(request, object_id)
        if campaign is None or not self.has_change_permission(request, campaign):
            messages.error(request, _('Not allowed.'))
        else:
            result = run_jobs_for_campaign(campaign)
            log_activity(
                request=request,
                action='other',
                message=f'Campaign jobs: {campaign.title} reminders={result["reminders"]}',
            )
            messages.success(
                request,
                _('Done — %s reminders, %s completed.') % (result['reminders'], result['completed']),
            )
        url = reverse('admin:properties_marketingcampaign_change', args=[object_id])
        return HttpResponse(headers={'HX-Redirect': url})


@admin.register(CampaignCollaborator)
class CampaignCollaboratorAdmin(UnfoldModelAdmin):
    brand_path = 'campaign__brand'
    list_display = ('campaign', 'user', 'role', 'can_edit', 'can_publish', 'accepted')
    autocomplete_fields = ('campaign', 'user')


@admin.register(SitePromotion)
class SitePromotionAdmin(UnfoldModelAdmin):
    list_display = ('title', 'brand', 'placement', 'is_active', 'sort_order')
    list_filter = (
        ('placement', ChoicesDropdownFilter),
        ('is_active', BooleanRadioFilter),
    )
    search_fields = ('title', 'description')
    autocomplete_fields = ('brand',)
