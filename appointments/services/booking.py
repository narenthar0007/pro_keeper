"""Create, approve, and manage appointments."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.brand_scoping import get_request_brand
from accounts.models import UserProfile  # noqa: F401 — used in resolve_owner_and_brand
from appointments.models import (
    Appointment,
    AppointmentAvailability,
    log_appointment_action,
    notify_host,
)
from appointments.services.slots import get_or_create_settings, slot_is_free
from hrms.services.scoping import get_owner_for_user


def resolve_owner_and_brand(user, request=None):
    role = None
    try:
        from accounts.privileges import get_user_role

        role = get_user_role(user)
    except Exception:
        pass
    if role == UserProfile.ROLE_OWNER:
        owner = user
    else:
        owner = get_owner_for_user(user) or user
    brand = get_request_brand(request) if request else None
    if brand is None:
        profile = getattr(user, 'profile', None)
        if profile:
            brand = profile.brand
    return owner, brand


def ensure_booking_slug(user):
    profile = user.profile
    if profile.booking_slug:
        return profile.booking_slug
    base = slugify(user.get_full_name() or user.username)[:24] or 'host'
    for _ in range(8):
        candidate = f'{base}-{secrets.token_hex(3)}'
        if not UserProfile.objects.filter(booking_slug=candidate).exists():
            profile.booking_slug = candidate
            profile.save(update_fields=['booking_slug'])
            return candidate
    token = secrets.token_urlsafe(16)
    profile.booking_slug = token[:64]
    profile.save(update_fields=['booking_slug'])
    return profile.booking_slug


def regenerate_booking_slug(user):
    profile = user.profile
    profile.booking_slug = None
    profile.save(update_fields=['booking_slug'])
    return ensure_booking_slug(user)


@transaction.atomic
def create_host_appointment(user, data, request=None):
    owner, brand = resolve_owner_and_brand(user, request)
    host = user
    on_date = data['appointment_date']
    start_time = data['start_time']
    end_time = data['end_time']
    if on_date < timezone.localdate():
        raise ValueError('Cannot book appointments in the past.')
    if not slot_is_free(host, on_date, start_time, end_time):
        raise ValueError('That time overlaps with another confirmed or pending appointment.')

    appt = Appointment.objects.create(
        host=host,
        owner=owner,
        brand=brand,
        title=data['title'],
        description=data.get('description', ''),
        appointment_date=on_date,
        start_time=start_time,
        end_time=end_time,
        guest_name=data.get('guest_name', ''),
        guest_email=data.get('guest_email', ''),
        guest_phone=data.get('guest_phone', ''),
        guest_company=data.get('guest_company', ''),
        appointment_type=data.get('appointment_type', Appointment.TYPE_OFFLINE),
        meeting_location=data.get('meeting_location', ''),
        meeting_link=data.get('meeting_link', ''),
        booked_by=Appointment.BOOKED_HOST,
        status=Appointment.STATUS_APPROVED,
        approved_by=user,
        approved_at=timezone.now(),
    )
    log_appointment_action(
        appt,
        actor=user,
        action='created_internal',
        new_status=Appointment.STATUS_APPROVED,
        description='Created by host (auto-approved)',
    )
    return appt


@transaction.atomic
def create_public_request(host, data):
    profile = host.profile
    if not profile.is_public_booking_active:
        raise ValueError('Public booking is disabled for this host.')
    settings = get_or_create_settings(host)
    on_date = data['appointment_date']
    start_time = data['start_time']
    end_time = data['end_time']
    if on_date < timezone.localdate():
        raise ValueError('Cannot book appointments in the past.')
    if not slot_is_free(host, on_date, start_time, end_time):
        raise ValueError('That slot is no longer available.')

    owner, brand = resolve_owner_and_brand(host, None)
    expires = timezone.now() + timedelta(hours=24)
    appt = Appointment.objects.create(
        host=host,
        owner=owner,
        brand=brand,
        title=data.get('title') or f'Meeting with {data["guest_name"]}',
        description=data.get('description', ''),
        appointment_date=on_date,
        start_time=start_time,
        end_time=end_time,
        guest_name=data['guest_name'],
        guest_email=data.get('guest_email', ''),
        guest_phone=data.get('guest_phone', ''),
        guest_company=data.get('guest_company', ''),
        appointment_type=data.get('appointment_type', Appointment.TYPE_OFFLINE),
        booked_by=Appointment.BOOKED_EXTERNAL,
        status=Appointment.STATUS_PENDING,
        reservation_expires_at=expires,
    )
    log_appointment_action(
        appt,
        actor=None,
        action='created_public',
        new_status=Appointment.STATUS_PENDING,
        description='Submitted via public booking link',
    )
    notify_host(
        appt,
        'new_request',
        'New appointment request',
        f'{appt.guest_name} requested {appt.appointment_date} {appt.start_time}.',
    )
    return appt


@transaction.atomic
def set_appointment_status(appt, user, new_status, *, reason=''):
    old = appt.status
    if new_status == Appointment.STATUS_APPROVED:
        if not slot_is_free(appt.host, appt.appointment_date, appt.start_time, appt.end_time, exclude_id=appt.pk):
            raise ValueError('Cannot approve: slot overlaps another appointment.')
        appt.status = Appointment.STATUS_APPROVED
        appt.approved_by = user
        appt.approved_at = timezone.now()
        appt.rejection_reason = ''
    elif new_status == Appointment.STATUS_REJECTED:
        appt.status = Appointment.STATUS_REJECTED
        appt.rejection_reason = reason or ''
    elif new_status == Appointment.STATUS_CANCELLED:
        appt.status = Appointment.STATUS_CANCELLED
        appt.cancelled_at = timezone.now()
    elif new_status == Appointment.STATUS_COMPLETED:
        appt.status = Appointment.STATUS_COMPLETED
        appt.completed_at = timezone.now()
    else:
        raise ValueError('Unsupported status transition.')
    appt.save()
    log_appointment_action(
        appt,
        actor=user,
        action=f'status_{new_status.lower()}',
        old_status=old,
        new_status=new_status,
        description=reason,
    )
    return appt


def replace_weekly_availability(host, rows):
    AppointmentAvailability.objects.filter(host=host).delete()
    created = []
    for row in rows:
        created.append(
            AppointmentAvailability.objects.create(
                host=host,
                day_of_week=row['day_of_week'],
                start_time=row['start_time'],
                end_time=row['end_time'],
                slot_duration_minutes=row.get('slot_duration_minutes', 30),
                is_active=row.get('is_active', True),
            )
        )
    return created
