"""Lead timeline helpers."""

from .models import LeadActivity


def log_lead_activity(enquiry, actor=None, verb='note', message=''):
    if enquiry is None:
        return None
    return LeadActivity.objects.create(
        enquiry=enquiry,
        brand=enquiry.brand,
        actor=actor,
        verb=verb,
        message=(message or '')[:500],
    )
