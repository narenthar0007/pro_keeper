"""Create pending rent rows for occupied units that have no payment this month."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from properties.models import Property, RentPayment, Tenant, month_start


class Command(BaseCommand):
    help = 'Create pending RentPayment rows for occupied rent units missing this month'

    def handle(self, *args, **options):
        today = timezone.localdate()
        start = month_start(today)
        created = 0
        props = Property.objects.filter(listing_type='rent', is_occupied=True)
        for prop in props:
            exists = prop.payments.filter(
                month_for__year=start.year,
                month_for__month=start.month,
            ).exists()
            if exists or not prop.monthly_rent:
                continue
            tenant = Tenant.objects.filter(property=prop, is_active=True).first()
            due = start
            RentPayment.objects.create(
                property=prop,
                tenant=tenant,
                amount=prop.monthly_rent,
                payment_date=today,
                month_for=start,
                due_date=due,
                status='pending',
                notes='Auto-generated pending rent',
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} pending rent row(s).'))
