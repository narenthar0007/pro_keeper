from datetime import datetime

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import UserProfile
from appointments.models import Appointment, AppointmentAvailability
from appointments.services.access import appointments_for_user, user_can_manage_appointments
from appointments.services.booking import (
    create_host_appointment,
    create_public_request,
    ensure_booking_slug,
    regenerate_booking_slug,
    replace_weekly_availability,
    set_appointment_status,
)
from appointments.services.slots import generate_slots_for_date, get_or_create_settings


def _deny_if_no_access(request):
    if not user_can_manage_appointments(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    return None


def _serialize_appointment(appt):
    return {
        'id': appt.pk,
        'reference': appt.reference_id,
        'title': appt.title,
        'description': appt.description,
        'appointment_date': appt.appointment_date.isoformat(),
        'start_time': appt.start_time.isoformat(),
        'end_time': appt.end_time.isoformat(),
        'guest_name': appt.guest_name,
        'guest_email': appt.guest_email,
        'guest_phone': appt.guest_phone,
        'booked_by': appt.booked_by,
        'status': appt.status,
        'appointment_type': appt.appointment_type,
    }


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def appointments_list_create(request):
    denied = _deny_if_no_access(request)
    if denied:
        return denied
    if request.method == 'GET':
        qs = appointments_for_user(request.user, request)
        status_filter = request.GET.get('status')
        q = (request.GET.get('search') or '').strip()
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if q:
            qs = qs.filter(title__icontains=q)
        if date_from:
            qs = qs.filter(appointment_date__gte=date_from)
        if date_to:
            qs = qs.filter(appointment_date__lte=date_to)
        return Response([_serialize_appointment(a) for a in qs[:500]])
    data = request.data
    try:
        payload = {
            'title': data.get('title'),
            'description': data.get('description', ''),
            'guest_name': data.get('guest_name', ''),
            'guest_email': data.get('guest_email', ''),
            'guest_phone': data.get('guest_phone', ''),
            'appointment_date': datetime.strptime(data['appointment_date'], '%Y-%m-%d').date(),
            'start_time': datetime.strptime(data['start_time'], '%H:%M').time()
            if len(data.get('start_time', '')) <= 5
            else datetime.strptime(data['start_time'], '%H:%M:%S').time(),
            'end_time': datetime.strptime(data['end_time'], '%H:%M').time()
            if len(data.get('end_time', '')) <= 5
            else datetime.strptime(data['end_time'], '%H:%M:%S').time(),
            'appointment_type': data.get('appointment_type', Appointment.TYPE_OFFLINE),
        }
        appt = create_host_appointment(request.user, payload, request)
    except (KeyError, ValueError) as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_serialize_appointment(appt), status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def appointment_status(request, pk):
    denied = _deny_if_no_access(request)
    if denied:
        return denied
    appt = get_object_or_404(appointments_for_user(request.user, request), pk=pk)
    new_status = (request.data.get('status') or '').upper()
    reason = request.data.get('reason', '')
    try:
        set_appointment_status(appt, request.user, new_status, reason=reason)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response(_serialize_appointment(appt))


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def availability_rules(request):
    denied = _deny_if_no_access(request)
    if denied:
        return denied
    if request.method == 'GET':
        rows = AppointmentAvailability.objects.filter(host=request.user, is_active=True)
        return Response(
            [
                {
                    'day_of_week': r.day_of_week,
                    'start_time': r.start_time.strftime('%H:%M'),
                    'end_time': r.end_time.strftime('%H:%M'),
                    'slot_duration_minutes': r.slot_duration_minutes,
                }
                for r in rows
            ]
        )
    rows_in = request.data if isinstance(request.data, list) else request.data.get('rows', [])
    parsed = []
    for row in rows_in:
        parsed.append(
            {
                'day_of_week': int(row['day_of_week']),
                'start_time': datetime.strptime(row['start_time'], '%H:%M').time()
                if len(row['start_time']) <= 5
                else datetime.strptime(row['start_time'], '%H:%M:%S').time(),
                'end_time': datetime.strptime(row['end_time'], '%H:%M').time()
                if len(row['end_time']) <= 5
                else datetime.strptime(row['end_time'], '%H:%M:%S').time(),
                'slot_duration_minutes': int(row.get('slot_duration_minutes', 30)),
            }
        )
    replace_weekly_availability(request.user, parsed)
    return Response({'ok': True})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_link(request):
    denied = _deny_if_no_access(request)
    if denied:
        return denied
    if request.data.get('regenerate'):
        slug = regenerate_booking_slug(request.user)
    else:
        slug = ensure_booking_slug(request.user)
    return Response({'booking_slug': slug})


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def public_booking_endpoint(request, booking_slug):
    profile = get_object_or_404(UserProfile, booking_slug=booking_slug)
    host = profile.user
    if not profile.is_public_booking_active:
        return Response({'detail': 'Booking disabled'}, status=status.HTTP_403_FORBIDDEN)
    settings_row = get_or_create_settings(host)
    if request.method == 'POST':
        data = request.data
        try:
            payload = {
                'guest_name': data['guest_name'],
                'guest_email': data.get('guest_email', ''),
                'guest_phone': data.get('guest_phone', ''),
                'title': data.get('title', ''),
                'description': data.get('description', ''),
                'appointment_date': datetime.strptime(data['appointment_date'], '%Y-%m-%d').date(),
                'start_time': datetime.strptime(data['start_time'], '%H:%M').time(),
                'end_time': datetime.strptime(data['end_time'], '%H:%M').time(),
            }
            appt = create_public_request(host, payload)
        except (KeyError, ValueError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {'reference': appt.reference_id, 'status': appt.status},
            status=status.HTTP_201_CREATED,
        )
    date_str = request.GET.get('date')
    slots = []
    if date_str:
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d').date()
            slots = generate_slots_for_date(host, d, settings=settings_row)
        except ValueError:
            slots = []
    return Response(
        {
            'host_name': settings_row.public_display_name or host.get_full_name() or host.username,
            'designation': settings_row.public_designation,
            'description': settings_row.public_description,
            'timezone': settings_row.timezone_name,
            'slots': slots,
        }
    )
