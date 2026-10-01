"""Rent pay / collect-rent reminders for owner and tenant accounts."""

from calendar import monthrange
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import UserProfile
from .privileges import get_user_role, has_privilege


def reminder_due_date(today, due_day):
    last = monthrange(today.year, today.month)[1]
    day = min(max(int(due_day or 1), 1), last)
    return date(today.year, today.month, day)


def reminder_window_start(due_date, days_before):
    return due_date - timedelta(days=max(0, int(days_before or 0)))


def is_in_reminder_window(profile, today=None):
    if not profile or not getattr(profile, 'rent_reminder_enabled', False):
        return False
    today = today or timezone.localdate()
    due = reminder_due_date(today, profile.rent_due_day)
    start = reminder_window_start(due, profile.reminder_days_before)
    return start <= today


def is_overdue(profile, today=None):
    today = today or timezone.localdate()
    return today > reminder_due_date(today, profile.rent_due_day)


def ordinal(n):
    n = int(n)
    if 10 <= n % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return suffix


def unpaid_items_for_user(user, today=None, brand=None):
    role = get_user_role(user)
    today = today or timezone.localdate()
    from properties.models import Tenant, month_start, properties_missing_rent_for_month

    if role == UserProfile.ROLE_OWNER:
        props = properties_missing_rent_for_month(user, for_date=today, brand=brand)
        return [{'title': prop.title, 'kind': 'property'} for prop in props]
    if role == UserProfile.ROLE_TENANT:
        start = month_start(today)
        profiles = Tenant.objects.filter(user=user, is_active=True).select_related('property')
        if brand is not None:
            profiles = profiles.filter(brand=brand)
        items = []
        for tenant in profiles:
            paid = tenant.payments.filter(
                month_for__year=start.year,
                month_for__month=start.month,
                status__in=['paid', 'partial'],
            ).exists()
            if not paid:
                items.append({'title': tenant.property.title, 'kind': 'home'})
        return items
    return []


def build_reminder_banner(user, today=None, brand=None):
    if not has_privilege(user, 'manage_rent_reminders'):
        return None
    profile = getattr(user, 'profile', None)
    if not is_in_reminder_window(profile, today):
        return None
    items = unpaid_items_for_user(user, today=today, brand=brand)
    if not items:
        return None
    overdue = is_overdue(profile, today)
    names = ', '.join(item['title'] for item in items[:4])
    if len(items) > 4:
        names += f' and {len(items) - 4} more'
    due_day = profile.rent_due_day
    due_label = f'{due_day}{ordinal(due_day)}'
    role = get_user_role(user)
    if role == UserProfile.ROLE_TENANT:
        title = 'Pay rent reminder'
        text = (
            f'Rent is overdue for {names}.'
            if overdue
            else f'Rent is due on the {due_label} for {names}.'
        )
    else:
        title = 'Collect rent reminder'
        text = (
            f'Rent is overdue — still unpaid: {names}.'
            if overdue
            else f'Collect rent by the {due_label}. Unpaid: {names}.'
        )
    return {
        'title': title,
        'text': text,
        'level': 'danger' if overdue else 'warning',
        'overdue': overdue,
    }


def maybe_send_rent_reminder(user, today=None, brand=None):
    if not has_privilege(user, 'manage_rent_reminders'):
        return False
    profile = getattr(user, 'profile', None)
    if not profile or not profile.rent_reminder_enabled or not profile.reminder_email_enabled:
        return False
    today = today or timezone.localdate()
    if not is_in_reminder_window(profile, today):
        return False
    last = profile.reminder_last_sent_on
    if last and last.year == today.year and last.month == today.month:
        return False
    email = (getattr(user, 'email', None) or '').strip()
    if not email:
        return False
    banner = build_reminder_banner(user, today=today, brand=brand)
    if not banner:
        return False
    send_mail(
        subject=f"PropKeep — {banner['title']}",
        message=banner['text'],
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=True,
    )
    profile.reminder_last_sent_on = today
    profile.save(update_fields=['reminder_last_sent_on'])
    return True


def send_due_rent_reminders(today=None, brand=None):
    today = today or timezone.localdate()
    qs = UserProfile.objects.filter(
        rent_reminder_enabled=True,
        reminder_email_enabled=True,
        role__in=[UserProfile.ROLE_OWNER, UserProfile.ROLE_TENANT],
    ).select_related('user')
    sent = 0
    for profile in qs:
        user = profile.user
        user.profile = profile
        if maybe_send_rent_reminder(user, today=today, brand=brand):
            sent += 1
    return sent
