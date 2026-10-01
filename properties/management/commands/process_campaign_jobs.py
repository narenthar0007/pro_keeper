from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date

from properties.campaign_jobs import run_campaign_jobs


class Command(BaseCommand):
    help = (
        'Background job: remind collaborators about missing daily photo/video posts, '
        'and mark campaigns completed when all posts are done and the end date has passed.'
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
        result = run_campaign_jobs(today=today)
        self.stdout.write(
            self.style.SUCCESS(
                f"Campaign jobs for {result['date']}: "
                f"{result['reminders']} reminder(s), "
                f"{result['completed']} campaign(s) completed."
            )
        )
