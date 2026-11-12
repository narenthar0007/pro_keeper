from django.conf import settings
from django.db import models


class MarketplaceListing(models.Model):
    """Owner-posted offers: products, services, skills, construction capacity, land rent."""

    KIND_PRODUCT = 'product'
    KIND_SERVICE = 'service'
    KIND_SKILL = 'skill'
    KIND_CONSTRUCTION = 'construction'
    KIND_LAND_RENT = 'land_rent'
    KIND_CHOICES = [
        (KIND_PRODUCT, 'Product for sale'),
        (KIND_SERVICE, 'Service'),
        (KIND_SKILL, 'Skills / freelance'),
        (KIND_CONSTRUCTION, 'Construction / project capacity'),
        (KIND_LAND_RENT, 'Land / plot for rent'),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='marketplace_listings',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='marketplace_listings',
    )
    property_link = models.ForeignKey(
        'properties.Property',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marketplace_listings',
        help_text='Optional link to an existing property listing',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=KIND_PRODUCT)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    price = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    price_label = models.CharField(
        max_length=80,
        blank=True,
        default='',
        help_text='e.g. per sqft, per month, negotiable',
    )
    capacity_sqft = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='For construction: e.g. 10000 sqft project capacity',
    )
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    image = models.ImageField(upload_to='marketplace/%Y/%m/', blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['brand', 'kind', 'is_published']),
            models.Index(fields=['owner', 'is_published']),
        ]

    def __str__(self):
        return self.title

    def get_kind_display_short(self):
        return dict(self.KIND_CHOICES).get(self.kind, self.kind)
