"""
Seed dummy data for PropKeep.

Usage:
    python manage.py seed_sample_data
    python manage.py seed_sample_data --clear
"""

from datetime import date, timedelta
from decimal import Decimal
from random import choice, randint, uniform

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import ActivityLog, Brand, UserProfile, ensure_default_privileges
from accounts.brands import ensure_default_brands
from properties.models import (
    Building,
    CampaignCollaborator,
    Complaint,
    Enquiry,
    Expense,
    MarketingCampaign,
    Property,
    PropertyShare,
    RentPayment,
    SitePromotion,
    Tenant,
    ensure_default_amenities,
)
from properties.marketing_permissions import ensure_owner_collaborator

CITIES = [
    ('Chennai', 'Tamil Nadu', '600001'),
    ('Bengaluru', 'Karnataka', '560001'),
    ('Hyderabad', 'Telangana', '500001'),
    ('Mumbai', 'Maharashtra', '400001'),
    ('Pune', 'Maharashtra', '411001'),
    ('Coimbatore', 'Tamil Nadu', '641001'),
    ('Madurai', 'Tamil Nadu', '625001'),
    ('Kochi', 'Kerala', '682001'),
]

STREETS = [
    'MG Road', 'Lake View Street', 'Park Avenue', 'Station Road',
    'Temple Street', 'Market Road', 'Ring Road', 'College Road',
]

LANDMARKS = [
    'Near Metro', 'Opp. City Mall', 'Behind Bus Stand', 'Next to Park',
    'Near Hospital', 'Close to School',
]

FIRST_NAMES = [
    'Arun', 'Priya', 'Karthik', 'Meena', 'Vikram', 'Anitha', 'Suresh',
    'Divya', 'Ravi', 'Lakshmi', 'Rahul', 'Sneha', 'Manoj', 'Kavya', 'Naveen',
]


class Command(BaseCommand):
    help = 'Create sample owners, tenants, properties, payments, and related dummy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete previously seeded sample_* users and related data first',
        )
        parser.add_argument('--owners', type=int, default=10)
        parser.add_argument('--tenants', type=int, default=15)
        parser.add_argument('--properties', type=int, default=40)

    def handle(self, *args, **options):
        ensure_default_privileges()
        ensure_default_brands()
        self.propkeep = Brand.objects.get(slug='propkeep')
        self.checkpro = Brand.objects.get(slug='checkpro-data')

        if options['clear']:
            self._clear_sample()

        owners_n = options['owners']
        tenants_n = options['tenants']
        props_n = options['properties']

        Group.objects.get_or_create(name='Owners')
        Group.objects.get_or_create(name='Tenants')
        Group.objects.get_or_create(name='Agents')

        owners = self._create_owners(owners_n)
        tenant_users = self._create_tenant_users(tenants_n)
        properties = self._create_properties(owners, props_n)
        buildings = self._create_buildings(owners, properties)
        tenants = self._create_tenants(properties, tenant_users)
        payments = self._create_payments(tenants)
        expenses = self._create_expenses(properties)
        enquiries = self._create_enquiries(properties)
        complaints = self._create_complaints(tenants)
        shares = self._create_shares(properties, owners)
        campaigns, promotions = self._create_marketing(properties, owners)
        logs = self._create_logs(owners + tenant_users)

        self.stdout.write(self.style.SUCCESS('Sample data created successfully.'))
        self.stdout.write('')
        self.stdout.write(f'  Owners:        {len(owners)}  (password: owner1234)')
        self.stdout.write(f'  Tenant users:   {len(tenant_users)}  (password: tenant1234)')
        self.stdout.write(f'  Properties:     {len(properties)}')
        self.stdout.write(f'  Buildings:      {len(buildings)}')
        self.stdout.write(f'  Tenant records: {len(tenants)}')
        self.stdout.write(f'  Rent payments:  {len(payments)}')
        self.stdout.write(f'  Expenses:       {len(expenses)}')
        self.stdout.write(f'  Enquiries:      {len(enquiries)}')
        self.stdout.write(f'  Complaints:     {len(complaints)}')
        self.stdout.write(f'  Property shares:{len(shares)}')
        self.stdout.write(f'  Campaigns:      {len(campaigns)}')
        self.stdout.write(f'  Promotions:     {len(promotions)}')
        self.stdout.write(f'  Activity logs:  {len(logs)}')
        total = (
            len(owners)
            + len(tenant_users)
            + len(properties)
            + len(tenants)
            + len(payments)
            + len(expenses)
            + len(enquiries)
            + len(complaints)
            + len(shares)
            + len(logs)
        )
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'  Approx. total rows added: {total}'))
        self.stdout.write('')
        self.stdout.write('Example logins:')
        self.stdout.write('  Owner  -> sample_owner1 / owner1234')
        self.stdout.write('  Tenant -> sample_tenant1 / tenant1234')

    def _clear_sample(self):
        sample_users = User.objects.filter(username__startswith='sample_')
        count = sample_users.count()
        # Properties owned by sample owners cascade tenants/payments/etc.
        Property.objects.filter(owner__in=sample_users).delete()
        ActivityLog.objects.filter(username__startswith='sample_').delete()
        sample_users.delete()
        self.stdout.write(self.style.WARNING(f'Cleared {count} sample_* users and related data.'))

    def _set_role(self, user, role, brand=None):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.brand = brand or self.propkeep
        user.is_staff = role == UserProfile.ROLE_ADMIN
        user.save()
        profile.save()
        return profile

    def _create_owners(self, n):
        owners = []
        owner_group = Group.objects.get(name='Owners')
        for i in range(1, n + 1):
            username = f'sample_owner{i}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@example.com'},
            )
            if created:
                user.set_password('owner1234')
                user.save()
            self._set_role(user, UserProfile.ROLE_OWNER)
            user.groups.add(owner_group)
            owners.append(user)
        return owners

    def _create_tenant_users(self, n):
        users = []
        tenant_group = Group.objects.get(name='Tenants')
        for i in range(1, n + 1):
            username = f'sample_tenant{i}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@example.com'},
            )
            if created:
                user.set_password('tenant1234')
                user.save()
            self._set_role(user, UserProfile.ROLE_TENANT)
            user.groups.add(tenant_group)
            users.append(user)
        return users

    def _create_properties(self, owners, n):
        properties = []
        types = [t[0] for t in Property.PROPERTY_TYPES]
        for i in range(1, n + 1):
            owner = owners[(i - 1) % len(owners)]
            city, state, pin = choice(CITIES)
            street = choice(STREETS)
            rent = Decimal(randint(8000, 45000))
            title = f'{choice(["Sunny", "Cozy", "Prime", "Green", "City"])} {choice(["2BHK", "1BHK", "3BHK", "Studio", "Villa"])} #{i}'
            brand = self.propkeep if i % 2 == 1 else self.checkpro
            is_sale = i % 5 == 0
            defaults = {
                'description': f'Sample listing {i} in {city}. Spacious and well connected.',
                'door_number': str(randint(1, 120)),
                'street': street,
                'landmark': choice(LANDMARKS),
                'address': f'{randint(1, 99)} {street}',
                'city': city,
                'state': state,
                'pincode': pin,
                'country': 'India',
                'latitude': Decimal(str(round(12.9 + uniform(-1, 1), 6))),
                'longitude': Decimal(str(round(77.5 + uniform(-2, 2), 6))),
                'contact_phone': f'91{randint(7000000000, 9999999999)}',
                'property_type': choice(types),
                'bedrooms': randint(1, 4),
                'bathrooms': randint(1, 3),
                'area_sqft': randint(400, 2200),
                'is_listed_publicly': choice([True, True, True, False]),
                'year_of_building': randint(1995, date.today().year),
            }
            if is_sale:
                defaults.update(
                    {
                        'listing_type': 'sale',
                        'sale_price': Decimal(randint(2500000, 15000000)),
                        'sale_status': 'available',
                        'monthly_rent': None,
                        'advance_amount': Decimal('0'),
                        'is_occupied': False,
                    }
                )
            else:
                defaults.update(
                    {
                        'listing_type': 'rent',
                        'monthly_rent': rent,
                        'advance_amount': rent * 3,
                        'is_occupied': False,
                    }
                )
            prop, created = Property.objects.get_or_create(
                owner=owner,
                title=title,
                brand=brand,
                defaults=defaults,
            )
            properties.append(prop)
        return properties

    def _create_buildings(self, owners, properties):
        ensure_default_amenities()
        buildings = []
        if not owners or not properties:
            return buildings
        owner = owners[0]
        brand = getattr(owner.profile, 'brand', None) or self.propkeep
        building, _ = Building.objects.get_or_create(
            owner=owner,
            name='Sample Green Residency',
            brand=brand,
            defaults={
                'address': '12 Lake View Street',
                'city': 'Chennai',
                'state': 'Tamil Nadu',
                'pincode': '600001',
                'country': 'India',
                'total_floors': 4,
                'year_of_building': 2018,
            },
        )
        units = [p for p in properties if p.owner_id == owner.id][:6]
        for idx, prop in enumerate(units, start=1):
            prop.building = building
            prop.unit_number = prop.unit_number or prop.door_number or str(idx)
            prop.floor_number = ((idx - 1) % 4) + 1
            prop.save(update_fields=['building', 'unit_number', 'floor_number'])
        buildings.append(building)
        return buildings

    def _create_tenants(self, properties, tenant_users):
        tenants = []
        # Occupy about 70% of properties
        for idx, prop in enumerate(properties):
            if prop.is_for_sale:
                continue
            if idx % 10 in (7, 8, 9):
                continue
            name = choice(FIRST_NAMES) + ' ' + choice(['Kumar', 'Raj', 'Devi', 'Singh', 'Nair', 'Iyer'])
            linked = tenant_users[idx % len(tenant_users)] if idx < len(tenant_users) * 2 else None
            # Prefer one active tenant per linked user when possible
            if linked and Tenant.objects.filter(user=linked, is_active=True).exists():
                linked = None
            move_in = date.today() - timedelta(days=randint(30, 600))
            tenant = Tenant.objects.create(
                property=prop,
                user=linked,
                name=name if not linked else linked.username.replace('sample_', '').title(),
                phone=f'9{randint(100000000, 999999999)}',
                email=linked.email if linked else f'tenant{idx}@example.com',
                move_in_date=move_in,
                lease_end_date=move_in + timedelta(days=365),
                notes='Sample tenant record',
                is_active=True,
                advance_paid=prop.advance_amount,
                advance_deduction=Decimal('0'),
                advance_refunded=Decimal('0'),
            )
            prop.is_occupied = True
            prop.save(update_fields=['is_occupied'])
            tenants.append(tenant)
        return tenants

    def _create_payments(self, tenants):
        payments = []
        statuses = ['paid', 'paid', 'paid', 'pending', 'partial', 'overdue']
        today = timezone.localdate()
        for tenant in tenants:
            # 3 months of rent history each
            for m in range(3):
                month_for = (today.replace(day=1) - timedelta(days=30 * m)).replace(day=1)
                payment = RentPayment.objects.create(
                    property=tenant.property,
                    tenant=tenant,
                    amount=tenant.property.monthly_rent if choice(statuses) != 'partial' else tenant.property.monthly_rent / 2,
                    payment_date=month_for + timedelta(days=randint(1, 10)),
                    month_for=month_for,
                    status=choice(statuses),
                    notes='Sample payment',
                )
                payments.append(payment)
        return payments

    def _create_expenses(self, properties):
        expenses = []
        categories = [c[0] for c in Expense.CATEGORY_CHOICES]
        titles = {
            'maintenance': 'Plumbing repair',
            'tax': 'Property tax',
            'repair': 'Painting work',
            'utility': 'Water bill',
            'other': 'Misc expense',
        }
        for prop in properties:
            for _ in range(randint(1, 3)):
                cat = choice(categories)
                expense = Expense.objects.create(
                    property=prop,
                    title=titles[cat],
                    category=cat,
                    amount=Decimal(randint(500, 15000)),
                    expense_date=date.today() - timedelta(days=randint(1, 180)),
                    notes='Sample expense',
                )
                expenses.append(expense)
        return expenses

    def _create_enquiries(self, properties):
        enquiries = []
        public_props = [p for p in properties if p.is_listed_publicly] or properties
        for i in range(25):
            prop = choice(public_props)
            enquiry = Enquiry.objects.create(
                property=prop,
                name=choice(FIRST_NAMES),
                email=f'buyer{i}@example.com',
                phone=f'98{randint(10000000, 99999999)}',
                message=f'Hi, is {prop.title} still available for visit?',
                is_read=choice([True, False]),
            )
            enquiries.append(enquiry)
        return enquiries

    def _create_complaints(self, tenants):
        complaints = []
        if not tenants:
            return complaints
        titles = ['Water leakage', 'Power issue', 'Noisy neighbor', 'Broken lock', 'AC not cooling']
        statuses = [s[0] for s in Complaint.STATUS_CHOICES]
        for i in range(min(20, len(tenants) * 2)):
            tenant = choice(tenants)
            complaint = Complaint.objects.create(
                property=tenant.property,
                tenant=tenant,
                created_by=tenant.user,
                title=choice(titles),
                description='Sample complaint created by seed command.',
                status=choice(statuses),
                owner_notes='Looking into it.' if choice([True, False]) else '',
            )
            complaints.append(complaint)
        return complaints

    def _create_shares(self, properties, owners):
        shares = []
        if len(owners) < 2:
            return shares
        for prop in properties[:10]:
            other = choice([o for o in owners if o.id != prop.owner_id])
            share, created = PropertyShare.objects.get_or_create(
                property=prop,
                user=other,
                defaults={'role': choice(['viewer', 'manager'])},
            )
            if created:
                shares.append(share)
        return shares

    def _create_marketing(self, properties, owners):
        campaigns = []
        promotions = []
        channels = [c[0] for c in MarketingCampaign.CHANNEL_CHOICES]
        rent_props = [p for p in properties if p.is_for_rent][:6]
        for idx, prop in enumerate(rent_props):
            campaign = MarketingCampaign.objects.create(
                property=prop,
                created_by=prop.owner,
                title=f'{prop.title} — {choice(["Summer push", "Festive promo", "Quick let"])}',
                channel=choice(channels),
                budget=Decimal(randint(2000, 25000)),
                spend=Decimal(randint(500, 8000)),
                status=choice(['draft', 'active', 'active', 'paused']),
                leads_count=randint(0, 12),
                notes='Sample marketing campaign',
            )
            ensure_owner_collaborator(campaign)
            campaigns.append(campaign)
            if idx == 0 and len(owners) > 1:
                other = choice([o for o in owners if o.id != prop.owner_id])
                CampaignCollaborator.objects.get_or_create(
                    campaign=campaign,
                    user=other,
                    defaults={
                        'role': 'creator',
                        'can_edit': True,
                        'can_publish': False,
                        'accepted': True,
                        'invited_by': prop.owner,
                    },
                )
        for brand in (self.propkeep, self.checkpro):
            promo = SitePromotion.objects.get_or_create(
                brand=brand,
                title=f'{brand.name} — Zero brokerage this month',
                defaults={
                    'description': 'List or browse properties with no brokerage fee this month.',
                    'cta_label': 'Browse listings',
                    'cta_url': 'http://127.0.0.1:8000/',
                    'placement': 'both',
                    'sort_order': 0,
                    'is_active': True,
                    'created_by': owners[0] if owners else None,
                },
            )[0]
            promotions.append(promo)
        return campaigns, promotions

    def _create_logs(self, users):
        logs = []
        paths = ['/', '/dashboard/', '/my-properties/', '/reports/', '/tenant-portal/', '/accounts/login/']
        actions = ['view', 'login', 'create', 'update', 'other']
        for i in range(30):
            user = choice(users)
            log = ActivityLog.objects.create(
                user=user,
                username=user.username,
                action=choice(actions),
                method=choice(['GET', 'POST']),
                path=choice(paths),
                status_code=choice([200, 200, 200, 302, 403]),
                ip_address='127.0.0.1',
                user_agent='SeedCommand/1.0',
                message=f'Sample activity log #{i + 1}',
            )
            logs.append(log)
        return logs
