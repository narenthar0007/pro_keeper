"""
Seed marketplace listings, public properties, and a sample business page.

Usage:
    python manage.py seed_marketplace_demo
    python manage.py seed_marketplace_demo --clear
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from accounts.brands import ensure_default_brands
from accounts.models import Brand, UserProfile, ensure_default_privileges
from marketplace.models import MarketplaceListing
from properties.models import Property, ensure_default_amenities
from storefront.models import OwnerStorefront, StorefrontProduct


DEMO_OWNER_USERNAME = 'market_demo'
DEMO_OWNER_PASSWORD = 'demo1234'
DEMO_TENANT_USERNAME = 'market_guest'
DEMO_TENANT_PASSWORD = 'demo1234'


class Command(BaseCommand):
    help = 'Create demo marketplace + business page data and print logins'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Remove demo marketplace/storefront rows for market_demo user',
        )

    def handle(self, *args, **options):
        ensure_default_privileges()
        ensure_default_brands()
        ensure_default_amenities()
        brand = Brand.objects.filter(is_default=True).first() or Brand.objects.first()

        if options['clear']:
            self._clear(brand)
            return

        owner = self._ensure_owner(brand)
        self._ensure_tenant(brand)
        listings = self._seed_listings(owner, brand)
        properties = self._seed_properties(owner, brand)
        site, products = self._seed_storefront(owner, brand)

        self.stdout.write(self.style.SUCCESS('Marketplace demo data ready.'))
        self.stdout.write('')
        self.stdout.write('Logins (same site URL you use locally or on PythonAnywhere):')
        self.stdout.write(f'  Owner  -> {DEMO_OWNER_USERNAME} / {DEMO_OWNER_PASSWORD}')
        self.stdout.write(f'  Tenant -> {DEMO_TENANT_USERNAME} / {DEMO_TENANT_PASSWORD}')
        self.stdout.write('')
        self.stdout.write('Pages to open:')
        self.stdout.write('  Marketplace browse     -> /marketplace/')
        self.stdout.write('  Owner: my offers       -> /marketplace/my/')
        self.stdout.write('  Owner: business pages  -> /business/')
        self.stdout.write(f'  Public storefront      -> {site.public_url_path}')
        self.stdout.write('')
        self.stdout.write(f'  Marketplace rows: {len(listings)}')
        self.stdout.write(f'  Demo properties (public): {len(properties)}')
        self.stdout.write(f'  Storefront products: {len(products)}')

    def _clear(self, brand):
        user = User.objects.filter(username=DEMO_OWNER_USERNAME).first()
        if user:
            MarketplaceListing.objects.filter(owner=user).delete()
            OwnerStorefront.objects.filter(owner=user).delete()
            Property.objects.filter(owner=user, title__startswith='[Demo]').delete()
        User.objects.filter(username__in=(DEMO_OWNER_USERNAME, DEMO_TENANT_USERNAME)).delete()
        self.stdout.write(self.style.WARNING('Cleared market_demo demo data and users.'))

    def _ensure_owner(self, brand):
        user, created = User.objects.get_or_create(
            username=DEMO_OWNER_USERNAME,
            defaults={'email': 'market_demo@example.com'},
        )
        if created:
            user.set_password(DEMO_OWNER_PASSWORD)
            user.save()
        else:
            user.set_password(DEMO_OWNER_PASSWORD)
            user.save(update_fields=['password'])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_OWNER
        profile.brand = brand
        profile.save()
        return user

    def _ensure_tenant(self, brand):
        user, created = User.objects.get_or_create(
            username=DEMO_TENANT_USERNAME,
            defaults={'email': 'market_guest@example.com'},
        )
        if created:
            user.set_password(DEMO_TENANT_PASSWORD)
            user.save()
        else:
            user.set_password(DEMO_TENANT_PASSWORD)
            user.save(update_fields=['password'])
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.ROLE_TENANT
        profile.brand = brand
        profile.save()

    def _seed_listings(self, owner, brand):
        samples = [
            {
                'kind': MarketplaceListing.KIND_CONSTRUCTION,
                'title': 'ABC Builders — up to 10,000 sqft commercial projects',
                'description': 'Turnkey construction. RCC, finishing, MEP. Coimbatore & nearby.',
                'city': 'Coimbatore',
                'price': Decimal('850'),
                'price_label': 'per sqft (indicative)',
                'capacity_sqft': 10000,
                'contact_phone': '919876543210',
            },
            {
                'kind': MarketplaceListing.KIND_PRODUCT,
                'title': 'Premium cotton kurta set (wholesale)',
                'description': 'Export-quality cotton dresses and kurta sets. MOQ 50 pieces.',
                'city': 'Tiruppur',
                'price': Decimal('450'),
                'price_label': 'per piece',
                'contact_phone': '919888877766',
            },
            {
                'kind': MarketplaceListing.KIND_SKILL,
                'title': 'Licensed electrician — industrial & residential',
                'description': '15 years experience. Available for contract or per-day hire.',
                'city': 'Chennai',
                'price': Decimal('1200'),
                'price_label': 'per day',
                'contact_phone': '919700011122',
            },
            {
                'kind': MarketplaceListing.KIND_LAND_RENT,
                'title': '2 acre vacant land — long lease',
                'description': 'Fenced plot on highway frontage. Suitable for warehouse or yard.',
                'city': 'Hosur',
                'price': Decimal('75000'),
                'price_label': 'per month',
                'contact_phone': '919611122233',
            },
            {
                'kind': MarketplaceListing.KIND_SERVICE,
                'title': 'Interior design & modular kitchen',
                'description': '3D design, execution, warranty on modular units.',
                'city': 'Bengaluru',
                'price': None,
                'price_label': 'Quote on site visit',
                'contact_phone': '919922233344',
            },
        ]
        created_rows = []
        for data in samples:
            row, _ = MarketplaceListing.objects.update_or_create(
                owner=owner,
                title=data['title'],
                defaults={
                    'brand': brand,
                    **data,
                    'is_published': True,
                },
            )
            created_rows.append(row)
        return created_rows

    def _seed_properties(self, owner, brand):
        props = []
        rent, _ = Property.objects.update_or_create(
            owner=owner,
            title='[Demo] 2BHK apartment — Peelamedu',
            defaults={
                'brand': brand,
                'description': 'Bright 2BHK near schools and IT parks.',
                'address': '12 Avinashi Road',
                'city': 'Coimbatore',
                'state': 'Tamil Nadu',
                'pincode': '641004',
                'property_type': 'apartment',
                'listing_type': 'rent',
                'monthly_rent': Decimal('18000'),
                'bedrooms': 2,
                'bathrooms': 2,
                'rooms': 3,
                'is_listed_publicly': True,
                'is_occupied': False,
            },
        )
        props.append(rent)
        sale, _ = Property.objects.update_or_create(
            owner=owner,
            title='[Demo] Residential plot — 2400 sqft',
            defaults={
                'brand': brand,
                'description': 'DTCP approved plot, ready for construction.',
                'address': 'Vadavalli Main Road',
                'city': 'Coimbatore',
                'state': 'Tamil Nadu',
                'pincode': '641041',
                'property_type': 'plot',
                'listing_type': 'sale',
                'sale_price': Decimal('4500000'),
                'sale_status': 'available',
                'area_sqft': 2400,
                'bedrooms': 0,
                'bathrooms': 0,
                'rooms': 0,
                'is_listed_publicly': True,
            },
        )
        props.append(sale)
        return props

    def _seed_storefront(self, owner, brand):
        site, _ = OwnerStorefront.objects.update_or_create(
            owner=owner,
            slug='mahi-textiles',
            defaults={
                'brand': brand,
                'business_name': 'Mahi Textiles',
                'tagline': 'Cotton wear for retail & wholesale',
                'about': (
                    'We manufacture and supply cotton dresses, kurta sets, and school uniforms. '
                    'Visit our unit in Tiruppur or order online via phone.'
                ),
                'contact_email': 'sales@mahi-textiles.demo',
                'contact_phone': '919876543210',
                'theme_color': '#0b5fff',
                'hero_image_url': 'https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&q=80',
                'is_published': True,
            },
        )
        product_samples = [
            (
                'Women cotton kurta',
                'Soft cotton, sizes S–XL',
                Decimal('599'),
                1,
                'https://images.unsplash.com/photo-1594935209851-22c2a0c0f0f1?w=600&q=80',
            ),
            (
                'Men formal shirt',
                'Office wear, multiple colors',
                Decimal('449'),
                2,
                'https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=600&q=80',
            ),
            (
                'School uniform set',
                'Shirt + pant/skirt',
                Decimal('899'),
                3,
                'https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600&q=80',
            ),
            (
                'Bulk kurta (50+ pcs)',
                'Wholesale rate',
                Decimal('380'),
                4,
                'https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=600&q=80',
            ),
        ]
        products = []
        for name, desc, price, order, img_url in product_samples:
            p, _ = StorefrontProduct.objects.update_or_create(
                storefront=site,
                name=name,
                defaults={
                    'description': desc,
                    'price': price,
                    'sort_order': order,
                    'is_active': True,
                    'image_url': img_url,
                },
            )
            products.append(p)
        return site, products
