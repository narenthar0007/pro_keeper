from django.conf import settings
from django.db import models
from django.utils.text import slugify


class OwnerStorefront(models.Model):
    """Mini e-commerce / showcase site for an owner's business."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='storefronts',
    )
    brand = models.ForeignKey(
        'accounts.Brand',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='storefronts',
    )
    business_name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80, unique=True)
    tagline = models.CharField(max_length=200, blank=True, default='')
    about = models.TextField(blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    theme_color = models.CharField(max_length=20, default='#0b5fff')
    logo = models.ImageField(upload_to='storefront/logos/%Y/%m/', blank=True, null=True)
    hero_image = models.ImageField(
        upload_to='storefront/hero/%Y/%m/',
        blank=True,
        null=True,
        help_text='Large banner at top of your public page (upload)',
    )
    hero_image_url = models.URLField(
        blank=True,
        default='',
        help_text='Or paste a hero image URL if you do not upload a file',
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['business_name']
        constraints = [
            models.UniqueConstraint(fields=['owner', 'slug'], name='storefront_owner_slug_uniq'),
        ]

    def __str__(self):
        return self.business_name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.business_name)[:60] or 'shop'
            candidate = base
            n = 1
            while OwnerStorefront.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f'{base}-{n}'
                n += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def public_url_path(self):
        return f'/w/{self.slug}/'

    @property
    def hero_display_url(self):
        if self.hero_image:
            return self.hero_image.url
        url = (self.hero_image_url or '').strip()
        return url or None

    @property
    def platform_brand_name(self):
        if self.brand_id:
            return self.brand.name
        return 'PropKeep'


class StorefrontProduct(models.Model):
    storefront = models.ForeignKey(
        OwnerStorefront,
        on_delete=models.CASCADE,
        related_name='products',
    )
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True, default='')
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='storefront/products/%Y/%m/', blank=True, null=True)
    image_url = models.URLField(
        blank=True,
        default='',
        help_text='Or paste a product image URL',
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name

    @property
    def display_image_url(self):
        if self.image:
            return self.image.url
        url = (self.image_url or '').strip()
        return url or None
