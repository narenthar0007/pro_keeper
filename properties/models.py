import builtins
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone

from accounts.brand_scoping import stamp_brand_from_property
from accounts.media_paths import (
    building_photo_upload,
    campaign_cover_upload,
    campaign_proof_upload,
    complaint_photo_upload,
    document_file_upload,
    enquiry_photo_upload,
    meter_photo_upload,
    promotion_image_upload,
    property_cover_upload,
    property_gallery_upload,
    tenant_lease_upload,
    tenant_photo_upload,
)

DEFAULT_AMENITIES = [
    ('lift', 'Lift'),
    ('parking', 'Parking'),
    ('power_backup', 'Power backup'),
    ('water', 'Water supply'),
    ('wifi', 'Wi-Fi'),
    ('security', 'Security'),
    ('gym', 'Gym'),
    ('cctv', 'CCTV'),
    ('ac', 'Air conditioning'),
    ('others', 'Others'),
]

OTHERS_AMENITY_CODE = 'others'


def ensure_default_amenities():
    for code, label in DEFAULT_AMENITIES:
        Amenity.objects.get_or_create(code=code, defaults={'label': label})


class Amenity(models.Model):
    code = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=80)

    class Meta:
        ordering = ['label']
        verbose_name_plural = 'amenities'

    def __str__(self):
        return self.label


class Building(models.Model):
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='buildings',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='buildings',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    street = models.CharField(max_length=100, blank=True, default='')
    landmark = models.CharField(max_length=100, blank=True, default='')
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, default='')
    pincode = models.CharField(max_length=6, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='India')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    year_of_building = models.PositiveIntegerField(
        validators=[MinValueValidator(1800), MaxValueValidator(date.today().year)],
        null=True,
        blank=True,
    )
    total_floors = models.PositiveSmallIntegerField(null=True, blank=True)
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='buildings')
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to=building_photo_upload, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['brand', 'owner']),
            models.Index(fields=['brand', 'city']),
        ]

    def __str__(self):
        return self.name

    def occupancy(self):
        units = self.units.all()
        total = units.count()
        occupied = units.filter(is_occupied=True).count()
        vacant = max(total - occupied, 0)
        percent = int(round((occupied / total) * 100)) if total else 0
        return {
            'total': total,
            'occupied': occupied,
            'vacant': vacant,
            'percent': percent,
        }

    def user_can_manage(self, user, brand=None):
        if not user.is_authenticated:
            return False
        if brand is not None and self.brand_id != brand.id:
            return False
        if self.owner_id == user.id or user.is_staff:
            return True
        return self.units.filter(Q(owner=user) | Q(shares__user=user)).exists()

    @classmethod
    def for_user(cls, user, brand=None):
        qs = cls.objects.filter(
            Q(owner=user) | Q(units__owner=user) | Q(units__shares__user=user)
        ).distinct()
        if brand is not None:
            qs = qs.filter(brand=brand)
        return qs

    @classmethod
    def for_brand(cls, brand):
        if brand is None:
            return cls.objects.none()
        return cls.objects.filter(brand=brand)


class Property(models.Model):
    PROPERTY_TYPES = [
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('villa', 'Villa'),
        ('pg', 'PG / Shared'),
        ('commercial', 'Commercial'),
        ('plot', 'Plot / Land'),
        ('other', 'Other'),
    ]
    LISTING_TYPE_CHOICES = [
        ('rent', 'For rent'),
        ('sale', 'For sale'),
    ]
    SALE_STATUS_CHOICES = [
        ('available', 'Available'),
        ('under_offer', 'Under offer'),
        ('sold', 'Sold'),
    ]
    FURNISHING_CHOICES = [
        ('unfurnished', 'Unfurnished'),
        ('semi', 'Semi-furnished'),
        ('fully', 'Fully furnished'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='properties',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='properties',
        help_text='Parent brand — properties (and related rows) are isolated per brand',
    )
    building = models.ForeignKey(
        Building,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='units',
        help_text='Optional parent building — leave empty for a standalone listing',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    door_number = models.CharField(max_length=100, blank=True, default='')
    unit_number = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='Unit / flat / room number within the building',
    )
    floor_number = models.PositiveSmallIntegerField(null=True, blank=True)
    street = models.CharField(max_length=100, blank=True, default='')
    landmark = models.CharField(max_length=100, blank=True, default='')
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True, default='')
    pincode = models.CharField(max_length=6, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='India')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='Phone for WhatsApp / public contact (digits with country code, e.g. 919876543210)',
    )
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES, default='apartment')
    bedrooms = models.PositiveIntegerField(default=1)
    bathrooms = models.PositiveIntegerField(default=1)
    rooms = models.PositiveIntegerField(default=1, help_text='Total number of rooms')
    kitchens = models.PositiveIntegerField(default=1)
    area_sqft = models.PositiveIntegerField(null=True, blank=True, help_text='Area in square feet')
    listing_type = models.CharField(
        max_length=10,
        choices=LISTING_TYPE_CHOICES,
        default='rent',
        help_text='Rent or sale — one type per property',
    )
    monthly_rent = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Required for rent listings',
    )
    sale_price = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Required for sale listings',
    )
    sale_status = models.CharField(
        max_length=20,
        choices=SALE_STATUS_CHOICES,
        default='available',
        blank=True,
    )
    price_negotiable = models.BooleanField(default=False)
    furnishing = models.CharField(
        max_length=20,
        choices=FURNISHING_CHOICES,
        blank=True,
        default='unfurnished',
    )
    possession_date = models.DateField(null=True, blank=True)
    allow_tenant_marketing = models.BooleanField(
        default=False,
        help_text='Allow linked tenants to create marketing campaigns for this property',
    )
    advance_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Security deposit / advance collected',
    )
    is_listed_publicly = models.BooleanField(
        default=True,
        help_text='Show this property on the public listings page',
    )
    is_occupied = models.BooleanField(default=False)
    planned_vacate_date = models.DateField(
        null=True,
        blank=True,
        help_text='Future date when the current tenant will vacate',
    )
    amenities = models.ManyToManyField(Amenity, blank=True, related_name='properties')
    late_fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Late fee charged after the grace period',
    )
    late_fee_grace_days = models.PositiveSmallIntegerField(
        default=3,
        help_text='Days after due date before late fee applies',
    )
    year_of_building = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1800),
            MaxValueValidator(date.today().year),
        ],
        null=True,
        blank=True,
    )
    featured_image = models.ImageField(
        upload_to=property_cover_upload,
        blank=True,
        null=True,
        help_text='Primary listing photo (gallery images are stored separately)',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'properties'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['brand', 'building']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['building', 'unit_number'],
                condition=Q(building__isnull=False) & ~Q(unit_number=''),
                name='uniq_building_unit_number',
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not (self.unit_number or '').strip() and (self.door_number or '').strip():
            self.unit_number = self.door_number.strip()
        super().save(*args, **kwargs)

    @property
    def unit_label(self):
        parts = []
        if self.building_id:
            parts.append(self.building.name)
        label = (self.unit_number or self.door_number or '').strip()
        if label:
            parts.append(label)
        elif self.floor_number is not None:
            parts.append(f'Floor {self.floor_number}')
        return ' · '.join(parts) if parts else self.title

    @property
    def current_tenant(self):
        return self.tenants.filter(is_active=True).first()

    @property
    def cover_image(self):
        """First gallery image marked cover (legacy helper)."""
        return self.images.order_by('-is_cover', 'id').first()

    def get_cover_url(self):
        if self.featured_image:
            return self.featured_image.url
        record = self.cover_image
        return record.image.url if record else ''

    @property
    def is_for_rent(self):
        return self.listing_type == 'rent'

    @property
    def is_for_sale(self):
        return self.listing_type == 'sale'

    @property
    def display_price(self):
        if self.is_for_sale and self.sale_price is not None:
            price = self.sale_price
            if price >= Decimal('10000000'):
                return f'₹{price / Decimal("10000000"):,.2f} Cr'
            if price >= Decimal('100000'):
                return f'₹{price / Decimal("100000"):,.2f} L'
            return f'₹{price:,.0f}'
        if self.monthly_rent is not None:
            return f'₹{self.monthly_rent:,.0f}/mo'
        return '—'

    def user_can_manage(self, user, brand=None):
        if not user.is_authenticated:
            return False
        if brand is not None and self.brand_id != brand.id:
            return False
        if self.owner_id == user.id or user.is_staff:
            return True
        return self.shares.filter(user=user).exists()

    @classmethod
    def for_user(cls, user, brand=None):
        qs = cls.objects.filter(Q(owner=user) | Q(shares__user=user)).distinct()
        if brand is not None:
            qs = qs.filter(brand=brand)
        return qs

    @classmethod
    def for_brand(cls, brand):
        if brand is None:
            return cls.objects.none()
        return cls.objects.filter(brand=brand)


class PropertyShare(models.Model):
    """Allow another user (agent/co-owner) to manage a property."""

    ROLE_CHOICES = [
        ('viewer', 'Viewer'),
        ('manager', 'Manager'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='property_shares',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='manager')
    commission_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text='Agent commission % on rent or sale for this share',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('property', 'user')

    def __str__(self):
        return f'{self.user} on {self.property}'


class PropertyImage(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to=property_gallery_upload)
    caption = models.CharField(max_length=200, blank=True)
    is_cover = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_cover', '-uploaded_at']

    def __str__(self):
        return f'Image for {self.property.title}'


class Tenant(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='tenants')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tenants',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_profiles',
        help_text='Link a login account for the tenant portal',
    )
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    move_in_date = models.DateField(null=True, blank=True)
    lease_end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    advance_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Advance / deposit actually collected from this tenant',
    )
    advance_deduction = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Amount deducted from advance (damages etc.)',
    )
    advance_refunded = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text='Amount returned to tenant',
    )
    lease_document = models.FileField(upload_to=tenant_lease_upload, blank=True, null=True)
    photo = models.ImageField(upload_to=tenant_photo_upload, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_active', '-move_in_date']

    def __str__(self):
        return f'{self.name} @ {self.property.title}'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        super().save(*args, **kwargs)

    @builtins.property
    def advance_balance(self):
        return self.advance_paid - self.advance_deduction - self.advance_refunded


class TenantJoinRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='join_requests')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='tenant_join_requests',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='property_join_requests',
    )
    message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'user'],
                condition=Q(status='pending'),
                name='uniq_pending_join_request',
            ),
        ]

    def __str__(self):
        return f'{self.user} → {self.property} ({self.status})'


class RentPayment(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('overdue', 'Overdue'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='payments')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='payments',
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    month_for = models.DateField(help_text='Any date in the month this rent covers')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='paid')
    due_date = models.DateField(null=True, blank=True)
    late_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-month_for', '-payment_date']

    def __str__(self):
        return f'{self.property.title} — {self.month_for:%b %Y} ({self.status})'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        super().save(*args, **kwargs)


class Expense(models.Model):
    CATEGORY_CHOICES = [
        ('maintenance', 'Maintenance'),
        ('tax', 'Tax'),
        ('repair', 'Repair'),
        ('utility', 'Utility'),
        ('other', 'Other'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='expenses')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='expenses',
    )
    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expense_date = models.DateField()
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f'{self.title} — {self.amount}'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        super().save(*args, **kwargs)


class Enquiry(models.Model):
    ENQUIRY_TYPE_CHOICES = [
        ('rent', 'Rent inquiry'),
        ('buy', 'Buy inquiry'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='enquiries')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='enquiries',
    )
    enquiry_type = models.CharField(
        max_length=10,
        choices=ENQUIRY_TYPE_CHOICES,
        default='rent',
    )
    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('visit_scheduled', 'Visit scheduled'),
        ('visit_done', 'Visit done'),
        ('offer', 'Offer'),
        ('negotiation', 'Negotiation'),
        ('converted', 'Converted'),
        ('lost', 'Lost'),
        ('closed', 'Closed'),
    ]
    SOURCE_CHOICES = [
        ('website', 'Website'),
        ('whatsapp', 'WhatsApp'),
        ('referral', 'Referral'),
        ('campaign', 'Campaign'),
        ('walk_in', 'Walk-in'),
        ('portal', 'Portal'),
        ('other', 'Other'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='website')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads',
    )
    campaign = models.ForeignKey(
        'MarketingCampaign',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enquiries',
    )
    owner_notes = models.TextField(blank=True)
    lost_reason = models.CharField(max_length=200, blank=True, default='')
    budget_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    preferred_move_in = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to=enquiry_photo_upload, blank=True, null=True)
    converted_tenant = models.ForeignKey(
        'Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_enquiries',
    )
    converted_deal = models.ForeignKey(
        'SaleDeal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='converted_from_enquiries',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'enquiries'
        indexes = [
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        return f'Enquiry from {self.name} on {self.property}'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        if self.property_id:
            self.enquiry_type = 'buy' if self.property.listing_type == 'sale' else 'rent'
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and self.campaign_id:
            MarketingCampaign.objects.filter(pk=self.campaign_id).update(
                leads_count=models.F('leads_count') + 1
            )


class MarketingCampaign(models.Model):
    CHANNEL_CHOICES = [
        ('magicbricks', 'MagicBricks'),
        ('99acres', '99acres'),
        ('housing', 'Housing.com'),
        ('facebook', 'Facebook'),
        ('instagram', 'Instagram'),
        ('whatsapp', 'WhatsApp'),
        ('olx', 'OLX'),
        ('website', 'Website'),
        ('referral', 'Referral'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
    ]

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name='marketing_campaigns',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='marketing_campaigns',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketing_campaigns_created',
    )
    title = models.CharField(max_length=200)
    channel = models.CharField(max_length=30, choices=CHANNEL_CHOICES)
    listing_url = models.URLField(blank=True, default='')
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    spend = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    leads_count = models.PositiveIntegerField(default=0)
    photos_per_day = models.PositiveIntegerField(
        default=0,
        help_text='How many photo posts collaborators should publish each day',
    )
    videos_per_day = models.PositiveIntegerField(
        default=0,
        help_text='How many video posts collaborators should publish each day',
    )
    content_reminder_note = models.TextField(
        blank=True,
        default='',
        help_text='Note included when reminding collaborators to create content for the seller',
    )
    notes = models.TextField(blank=True)
    cover_image = models.ImageField(upload_to=campaign_cover_upload, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['property', 'status']),
        ]

    def __str__(self):
        return f'{self.title} ({self.get_channel_display()})'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        super().save(*args, **kwargs)

    # Note: this model has a FK named `property`, which shadows the built-in
    # @property decorator — use methods instead of @property here.
    def schedule_days(self):
        if not self.start_date or not self.end_date:
            return 0
        if self.end_date < self.start_date:
            return 0
        return (self.end_date - self.start_date).days + 1

    def total_photos_required(self):
        return self.schedule_days() * self.photos_per_day

    def total_videos_required(self):
        return self.schedule_days() * self.videos_per_day

    def content_totals(self):
        from django.db.models import Sum

        totals = self.content_logs.aggregate(
            photos=Sum('photos_count'),
            videos=Sum('videos_count'),
        )
        return {
            'photos': totals['photos'] or 0,
            'videos': totals['videos'] or 0,
        }

    def content_done_for_date(self, day):
        from django.db.models import Sum

        totals = self.content_logs.filter(work_date=day).aggregate(
            photos=Sum('photos_count'),
            videos=Sum('videos_count'),
        )
        return {
            'photos': totals['photos'] or 0,
            'videos': totals['videos'] or 0,
        }

    def is_content_complete(self):
        photos_needed = self.total_photos_required()
        videos_needed = self.total_videos_required()
        if photos_needed == 0 and videos_needed == 0:
            return False
        totals = self.content_totals()
        return (
            totals['photos'] >= photos_needed
            and totals['videos'] >= videos_needed
        )

    def should_auto_complete(self, today=None):
        from django.utils import timezone

        today = today or timezone.localdate()
        if self.status != 'active':
            return False
        if not self.end_date or self.end_date > today:
            return False
        return self.is_content_complete()


class CampaignCollaborator(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('editor', 'Editor'),
        ('creator', 'Creator'),
        ('viewer', 'Viewer'),
    ]

    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        related_name='collaborators',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='campaign_collaborations',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    can_edit = models.BooleanField(default=False)
    can_publish = models.BooleanField(default=False)
    accepted = models.BooleanField(default=False)
    invite_message = models.TextField(
        blank=True,
        default='',
        help_text='Message from campaign owner when inviting this collaborator',
    )
    is_read = models.BooleanField(
        default=False,
        help_text='Invitee has opened or responded to this collaboration request',
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaign_invites_sent',
    )
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('campaign', 'user')
        ordering = ['-can_publish', 'role', 'invited_at']

    def __str__(self):
        return f'{self.user.username} on {self.campaign.title}'


class CampaignContentLog(models.Model):
    """Daily photo/video posts logged by collaborators for a campaign."""

    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        related_name='content_logs',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='campaign_content_logs',
    )
    work_date = models.DateField()
    photos_count = models.PositiveIntegerField(default=0)
    videos_count = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True, default='')
    proof_image = models.ImageField(upload_to=campaign_proof_upload, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-work_date', '-created_at']
        unique_together = ('campaign', 'user', 'work_date')
        indexes = [
            models.Index(fields=['campaign', 'work_date']),
        ]

    def __str__(self):
        return f'{self.campaign.title} · {self.work_date} · {self.user.username}'


class CampaignTaskMessage(models.Model):
    """Inbox message for collaborators (e.g. background reminder to post content)."""

    campaign = models.ForeignKey(
        MarketingCampaign,
        on_delete=models.CASCADE,
        related_name='task_messages',
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='campaign_task_messages',
    )
    work_date = models.DateField(
        help_text='The day this reminder is about',
    )
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('campaign', 'recipient', 'work_date')
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]

    def __str__(self):
        return f'Reminder for {self.recipient.username} · {self.campaign.title}'


class SitePromotion(models.Model):
    PLACEMENT_CHOICES = [
        ('homepage', 'Homepage'),
        ('marketing_page', 'Marketing page'),
        ('both', 'Both'),
    ]

    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='site_promotions',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='site_promotions_created',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to=promotion_image_upload, blank=True, null=True)
    cta_label = models.CharField(max_length=80, blank=True, default='')
    cta_url = models.URLField(blank=True, default='')
    placement = models.CharField(max_length=20, choices=PLACEMENT_CHOICES, default='marketing_page')
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', '-created_at']
        indexes = [
            models.Index(fields=['brand', 'is_active', 'sort_order']),
        ]

    def __str__(self):
        return self.title

    def is_currently_active(self, on_date=None):
        if not self.is_active:
            return False
        on_date = on_date or timezone.localdate()
        if self.start_date and on_date < self.start_date:
            return False
        if self.end_date and on_date > self.end_date:
            return False
        return True


class Complaint(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_progress', 'In progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='complaints')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='complaints',
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints_created',
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    CATEGORY_CHOICES = [
        ('plumbing', 'Plumbing'),
        ('electrical', 'Electrical'),
        ('civil', 'Civil'),
        ('other', 'Other'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
    ]
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    photo = models.ImageField(upload_to=complaint_photo_upload, blank=True, null=True)
    building = models.ForeignKey(
        Building,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='complaints',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    owner_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.status})'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        if self.property_id and not self.building_id:
            self.building_id = self.property.building_id
        super().save(*args, **kwargs)


class LeadVisit(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('no_show', 'No show'),
        ('cancelled', 'Cancelled'),
    ]

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='visits')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='lead_visits')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='lead_visits',
    )
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_visits_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f'Visit {self.enquiry.name} @ {self.property.title}'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        super().save(*args, **kwargs)
        if self.status == 'scheduled' and self.enquiry.status in ('new', 'contacted'):
            Enquiry.objects.filter(pk=self.enquiry_id).update(status='visit_scheduled')
        elif self.status == 'completed' and self.enquiry.status in (
            'new',
            'contacted',
            'visit_scheduled',
        ):
            Enquiry.objects.filter(pk=self.enquiry_id).update(status='visit_done')


class Offer(models.Model):
    TYPE_CHOICES = [
        ('rent', 'Rent'),
        ('sale', 'Sale'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('countered', 'Countered'),
        ('withdrawn', 'Withdrawn'),
    ]

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='offers')
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='offers')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='offers',
    )
    offer_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='sale')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    valid_until = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='offers_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Offer ₹{self.amount} on {self.property.title}'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        super().save(*args, **kwargs)
        if self.status == 'accepted' and self.property.is_for_sale:
            Property.objects.filter(pk=self.property_id).update(sale_status='under_offer')
            Enquiry.objects.filter(pk=self.enquiry_id).update(status='offer')
        elif self.status == 'pending':
            Enquiry.objects.filter(pk=self.enquiry_id, status__in=['new', 'contacted', 'visit_done']).update(
                status='offer'
            )


class SaleDeal(models.Model):
    STATUS_CHOICES = [
        ('token', 'Token'),
        ('agreement', 'Agreement'),
        ('registered', 'Registered'),
        ('cancelled', 'Cancelled'),
    ]

    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='sale_deals')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sale_deals',
    )
    enquiry = models.ForeignKey(
        Enquiry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_deals',
    )
    offer = models.ForeignKey(
        Offer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deals',
    )
    buyer_name = models.CharField(max_length=150)
    buyer_phone = models.CharField(max_length=20, blank=True, default='')
    buyer_email = models.EmailField(blank=True, default='')
    agreed_price = models.DecimalField(max_digits=14, decimal_places=2)
    token_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    token_date = models.DateField(null=True, blank=True)
    agreement_date = models.DateField(null=True, blank=True)
    registration_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='token')
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    commission_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_deals_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Deal {self.buyer_name} · {self.property.title}'

    def save(self, *args, **kwargs):
        stamp_brand_from_property(self)
        if self.commission_percent and not self.commission_amount and self.agreed_price:
            self.commission_amount = (
                self.agreed_price * self.commission_percent / Decimal('100')
            ).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)
        if self.status == 'registered':
            Property.objects.filter(pk=self.property_id).update(
                sale_status='sold',
                is_listed_publicly=False,
            )
        elif self.status in ('token', 'agreement'):
            Property.objects.filter(pk=self.property_id).exclude(sale_status='sold').update(
                sale_status='under_offer'
            )
        elif self.status == 'cancelled':
            other = Offer.objects.filter(
                property_id=self.property_id,
                status='accepted',
            ).exclude(pk=self.offer_id or 0).exists()
            if not other:
                Property.objects.filter(pk=self.property_id, sale_status='under_offer').update(
                    sale_status='available'
                )


class LeadActivity(models.Model):
    VERB_CHOICES = [
        ('created', 'Created'),
        ('status_changed', 'Status changed'),
        ('visit', 'Visit'),
        ('offer', 'Offer'),
        ('note', 'Note'),
        ('converted', 'Converted'),
    ]

    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='activities')
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='lead_activities',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_activities',
    )
    verb = models.CharField(max_length=20, choices=VERB_CHOICES, default='note')
    message = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.verb} · {self.enquiry_id}'


class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ('lease', 'Lease'),
        ('id_proof', 'ID proof'),
        ('aadhaar', 'Aadhaar'),
        ('pan', 'PAN'),
        ('invoice', 'Invoice'),
        ('sale_agreement', 'Sale agreement'),
        ('other', 'Other'),
    ]

    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='documents',
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='documents',
    )
    building = models.ForeignKey(
        Building,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
    )
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
    )
    deal = models.ForeignKey(
        SaleDeal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='documents',
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents',
    )
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, default='other')
    file = models.FileField(upload_to=document_file_upload)
    title = models.CharField(max_length=200)
    expires_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class UserNotification(models.Model):
    KIND_CHOICES = [
        ('rent_due', 'Rent due'),
        ('enquiry', 'Enquiry'),
        ('visit', 'Visit'),
        ('offer', 'Offer'),
        ('complaint', 'Complaint'),
        ('campaign_invite', 'Campaign invite'),
        ('campaign_task', 'Campaign task'),
        ('lease_expiry', 'Lease expiry'),
        ('message', 'Message'),
        ('join_request', 'Join request'),
        ('admin_message', 'Admin message'),
        ('rent_reminder', 'Rent reminder'),
    ]

    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='notifications',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    url = models.CharField(max_length=400, blank=True, default='')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f'{self.user} · {self.title}'


class MessageThread(models.Model):
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='message_threads',
    )
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='message_threads')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='message_threads')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('property', 'tenant')
        ordering = ['-created_at']

    def __str__(self):
        return f'Thread {self.tenant} @ {self.property}'


class Message(models.Model):
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages',
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Message {self.pk}'


class MeterReading(models.Model):
    METER_CHOICES = [
        ('electricity', 'Electricity'),
        ('water', 'Water'),
    ]

    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='meter_readings',
    )
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='meter_readings')
    meter_type = models.CharField(max_length=20, choices=METER_CHOICES, default='electricity')
    reading_value = models.DecimalField(max_digits=12, decimal_places=2)
    reading_date = models.DateField()
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    photo = models.ImageField(upload_to=meter_photo_upload, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meter_readings_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reading_date', '-created_at']

    def __str__(self):
        return f'{self.get_meter_type_display()} {self.reading_value} @ {self.property}'


class PaymentOrder(models.Model):
    GATEWAY_CHOICES = [
        ('manual', 'Manual / simulated'),
        ('upi', 'UPI'),
        ('razorpay', 'Razorpay'),
    ]
    STATUS_CHOICES = [
        ('created', 'Created'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='payment_orders',
    )
    rent_payment = models.ForeignKey(
        RentPayment,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, default='manual')
    gateway_order_id = models.CharField(max_length=80, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')
    raw_payload = models.JSONField(blank=True, default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order {self.pk} {self.status}'


class SavedListing(models.Model):
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='saved_listings',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_listings',
    )
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'property')
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} saved {self.property}'


class CommissionPayout(models.Model):
    STATUS_CHOICES = [
        ('due', 'Due'),
        ('paid', 'Paid'),
    ]

    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        related_name='commission_payouts',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='commission_payouts',
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='commission_payouts',
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    period = models.CharField(max_length=40, blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='due')
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} · ₹{self.amount}'


def month_start(d=None):
    d = d or timezone.localdate()
    return d.replace(day=1)


def properties_missing_rent_for_month(user, for_date=None, brand=None):
    """Occupied properties owned/shared by user with no paid/partial rent this month."""
    start = month_start(for_date)
    props = Property.for_user(user, brand=brand).filter(
        listing_type='rent',
        is_occupied=True,
    )
    due = []
    for prop in props:
        paid = prop.payments.filter(
            month_for__year=start.year,
            month_for__month=start.month,
            status__in=['paid', 'partial'],
        ).exists()
        if not paid:
            due.append(prop)
    return due


def income_expense_for_month(user, year, month, brand=None):
    props = Property.for_user(user, brand=brand).filter(listing_type='rent')
    income = (
        RentPayment.objects.filter(
            property__in=props,
            status='paid',
            month_for__year=year,
            month_for__month=month,
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )
    expenses = (
        Expense.objects.filter(
            property__in=props,
            expense_date__year=year,
            expense_date__month=month,
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0')
    )
    return income, expenses, income - expenses
