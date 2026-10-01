from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from accounts.reminders import send_due_rent_reminders


class Command(BaseCommand):
    help = (
        'Email owner/tenant rent reminders that are due today '
        '(pay-rent for tenants, collect-rent for owners).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            help='Process as this date (YYYY-MM-DD). Defaults to today.',
        )

    def handle(self, *args, **options):
        today = None
        if options.get('date'):
            today = parse_date(options['date'])
            if today is None:
                self.stderr.write(self.style.ERROR('Invalid --date; use YYYY-MM-DD'))
                return
        sent = send_due_rent_reminders(today=today)
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} rent reminder email(s).'))
