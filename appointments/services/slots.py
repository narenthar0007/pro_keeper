"""Compute available slots for a host on a given date."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.utils import timezone

from appointments.models import Appointment, AppointmentAvailability, AppointmentHoliday, AppointmentSettings


def get_or_create_settings(host):
    row, _ = AppointmentSettings.objects.get_or_create(host=host)
    return row


def _combine(d: date, t: time, tz):
    naive = datetime.combine(d, t)
    if timezone.is_naive(naive):
        return timezone.make_aware(naive, tz)
    return naive.astimezone(tz)


def _intervals_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def _blocking_statuses(settings):
    statuses = [Appointment.STATUS_APPROVED]
    if settings.pending_blocks_slot:
        statuses.append(Appointment.STATUS_PENDING)
    return statuses


def existing_appointments_for_date(host, on_date, settings):
    statuses = _blocking_statuses(settings)
    return Appointment.objects.filter(
        host=host,
        appointment_date=on_date,
        status__in=statuses,
    )


def is_holiday_blocked(host, on_date, slot_start, slot_end):
    holidays = AppointmentHoliday.objects.filter(host=host, holiday_date=on_date)
    for h in holidays:
        if h.is_full_day:
            return True
        if h.start_time and h.end_time:
            if slot_start < h.end_time and h.start_time < slot_end:
                return True
    return False


def generate_slots_for_date(host, on_date: date, *, settings=None):
    settings = settings or get_or_create_settings(host)
    tz = timezone.get_current_timezone()
    today = timezone.localdate()
    if on_date < today:
        return []
    max_date = today + timedelta(days=settings.maximum_advance_days)
    if on_date > max_date:
        return []

    weekday = on_date.weekday()
    # Python: Monday=0 … convert to spec Sunday=0
    day_of_week = (weekday + 1) % 7

    avail_rows = AppointmentAvailability.objects.filter(
        host=host,
        day_of_week=day_of_week,
        is_active=True,
    )
    if not avail_rows.exists():
        return []

    now = timezone.localtime()
    min_start = now + timedelta(hours=settings.minimum_notice_hours)

    booked = list(existing_appointments_for_date(host, on_date, settings))
    slots = []
    duration = timedelta(minutes=settings.slot_duration_minutes)
    buffer = timedelta(minutes=settings.buffer_minutes)

    for row in avail_rows:
        cursor = datetime.combine(on_date, row.start_time)
        end_bound = datetime.combine(on_date, row.end_time)
        if timezone.is_naive(cursor):
            cursor = timezone.make_aware(cursor, tz)
            end_bound = timezone.make_aware(end_bound, tz)
        slot_len = timedelta(minutes=row.slot_duration_minutes or settings.slot_duration_minutes)
        while cursor + slot_len <= end_bound:
            slot_end = cursor + slot_len
            st = cursor.time()
            et = slot_end.time()
            if is_holiday_blocked(host, on_date, st, et):
                cursor = slot_end + buffer
                continue
            if _combine(on_date, st, tz) < min_start:
                cursor = slot_end + buffer
                continue
            conflict = False
            for appt in booked:
                if _intervals_overlap(st, et, appt.start_time, appt.end_time):
                    conflict = True
                    break
            if not conflict:
                slots.append(
                    {
                        'start_time': st.strftime('%H:%M'),
                        'end_time': et.strftime('%H:%M'),
                        'start_time_iso': st.isoformat(),
                        'end_time_iso': et.isoformat(),
                    }
                )
            cursor = slot_end + buffer
    return slots


def slot_is_free(host, on_date, start_time, end_time, *, exclude_id=None):
    settings = get_or_create_settings(host)
    if is_holiday_blocked(host, on_date, start_time, end_time):
        return False
    statuses = _blocking_statuses(settings)
    qs = Appointment.objects.filter(
        host=host,
        appointment_date=on_date,
        status__in=statuses,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    for appt in qs:
        if _intervals_overlap(start_time, end_time, appt.start_time, appt.end_time):
            return False
    return True
