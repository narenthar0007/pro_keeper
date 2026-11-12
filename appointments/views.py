from datetime import timedelta

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from accounts.models import UserProfile
from accounts.ui_components import build_button, build_kpis, build_page_header
from accounts.ui_table import build_table

from appointments.decorators import appointments_manage_required
from appointments.forms import AppointmentCreateForm, AppointmentSettingsForm, PublicBookingForm
from appointments.models import Appointment, AppointmentAvailability
from appointments.services.access import appointments_for_user
from appointments.services.booking import (
    create_host_appointment,
    create_public_request,
    ensure_booking_slug,
    regenerate_booking_slug,
    replace_weekly_availability,
    set_appointment_status,
)
from appointments.services.slots import generate_slots_for_date, get_or_create_settings


def _status_badge(status):
    colors = {
        Appointment.STATUS_PENDING: 'warn',
        Appointment.STATUS_APPROVED: 'ok',
        Appointment.STATUS_REJECTED: 'danger',
        Appointment.STATUS_CANCELLED: 'muted',
        Appointment.STATUS_COMPLETED: 'muted',
    }
    return colors.get(status, 'default')


@appointments_manage_required
def dashboard(request):
    qs = appointments_for_user(request.user, request)
    today = timezone.localdate()
    week_end = today + timedelta(days=7)

    status = (request.GET.get('status') or '').strip()
    q = (request.GET.get('q') or '').strip()
    date_filter = (request.GET.get('range') or 'all').strip()

    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(guest_name__icontains=q)
            | Q(guest_email__icontains=q)
            | Q(guest_phone__icontains=q)
        )
    if date_filter == 'today':
        qs = qs.filter(appointment_date=today)
    elif date_filter == 'week':
        qs = qs.filter(appointment_date__gte=today, appointment_date__lte=week_end)
    elif date_filter == 'month':
        month_end = today.replace(day=28) + timedelta(days=4)
        month_end = month_end - timedelta(days=month_end.day)
        qs = qs.filter(appointment_date__gte=today.replace(day=1), appointment_date__lte=month_end)

    base_qs = appointments_for_user(request.user, request)
    kpis = build_kpis(
        [
            {'label': 'Total', 'value': base_qs.count()},
            {
                'label': 'Upcoming',
                'value': base_qs.filter(
                    appointment_date__gte=today,
                    status=Appointment.STATUS_APPROVED,
                ).count(),
            },
            {
                'label': 'Pending',
                'value': base_qs.filter(status=Appointment.STATUS_PENDING).count(),
            },
            {
                'label': 'Completed',
                'value': base_qs.filter(status=Appointment.STATUS_COMPLETED).count(),
            },
            {
                'label': 'Cancelled',
                'value': base_qs.filter(status=Appointment.STATUS_CANCELLED).count(),
            },
        ]
    )

    profile = request.user.profile
    slug = profile.booking_slug or ''
    if not slug:
        slug = ensure_booking_slug(request.user)
    booking_url = request.build_absolute_uri(reverse('public_book', args=[slug]))

    page_header = build_page_header(
        title='Appointments',
        subtitle='Manage bookings and share your public link',
        actions=[
            build_button('Create appointment', href=reverse('appointments_create'), variant='primary'),
            build_button('Availability settings', href=reverse('appointments_settings'), variant='secondary'),
            build_button('Calendar', href=reverse('appointments_calendar'), variant='secondary'),
        ],
    )

    rows = []
    for appt in qs[:200]:
        actions = [
            f'<a href="{reverse("appointments_detail", args=[appt.pk])}">View</a>',
        ]
        if appt.status == Appointment.STATUS_PENDING:
            actions.append(f'<a href="{reverse("appointments_detail", args=[appt.pk])}#approve">Approve</a>')
        rows.append(
            {
                'ref': appt.reference_id,
                'title': appt.title,
                'visitor': appt.guest_name or '—',
                'contact': appt.guest_phone or '—',
                'email': appt.guest_email or '—',
                'date': appt.appointment_date.isoformat(),
                'start': appt.start_time.strftime('%H:%M'),
                'end': appt.end_time.strftime('%H:%M'),
                'type': appt.get_appointment_type_display(),
                'source': appt.get_booked_by_display(),
                'status': appt.get_status_display(),
                'status_kind': _status_badge(appt.status),
                'actions': ' · '.join(actions),
            }
        )

    table = build_table(
        id='appointments-main',
        columns=[
            {'key': 'ref', 'label': 'ID'},
            {'key': 'title', 'label': 'Title'},
            {'key': 'visitor', 'label': 'Visitor'},
            {'key': 'contact', 'label': 'Phone'},
            {'key': 'email', 'label': 'Email'},
            {'key': 'date', 'label': 'Date'},
            {'key': 'start', 'label': 'Start'},
            {'key': 'end', 'label': 'End'},
            {'key': 'type', 'label': 'Type', 'badge': True},
            {'key': 'source', 'label': 'Source', 'badge': True},
            {'key': 'status', 'label': 'Status', 'badge': True, 'badge_key': 'status_kind'},
            {'key': 'actions', 'label': '', 'html': True},
        ],
        rows=rows,
        empty_text='No appointments yet. Create one or share your booking link.',
    )

    pending = base_qs.filter(status=Appointment.STATUS_PENDING).order_by('appointment_date')[:20]

    return render(
        request,
        'appointments/dashboard.html',
        {
            'page_header': page_header,
            'kpis': kpis,
            'table': table,
            'booking_url': booking_url,
            'booking_active': profile.is_public_booking_active,
            'pending': pending,
            'status_filter': status,
            'q': q,
            'range_filter': date_filter,
        },
    )


@appointments_manage_required
def create_appointment(request):
    form = AppointmentCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            create_host_appointment(request.user, form.cleaned_data, request)
            messages.success(request, 'Appointment created and confirmed.')
            return redirect('appointments_dashboard')
        except ValueError as exc:
            messages.error(request, str(exc))
    page_header = build_page_header(
        title='Create appointment',
        subtitle='Internal bookings are confirmed immediately',
    )
    return render(
        request,
        'appointments/form_page.html',
        {'page_header': page_header, 'form': form, 'submit_label': 'Save appointment'},
    )


@appointments_manage_required
def settings_view(request):
    settings_row = get_or_create_settings(request.user)
    form = AppointmentSettingsForm(request.POST or None, instance=settings_row)
    availabilities = AppointmentAvailability.objects.filter(host=request.user)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Booking settings saved.')
        return redirect('appointments_settings')

    if request.method == 'POST' and request.POST.get('action') == 'save_availability':
        from datetime import datetime

        rows = []
        for day in range(7):
            if not request.POST.get(f'day_{day}_enabled'):
                continue
            st = request.POST.get(f'day_{day}_start') or '09:00'
            et = request.POST.get(f'day_{day}_end') or '17:00'
            rows.append(
                {
                    'day_of_week': day,
                    'start_time': datetime.strptime(st, '%H:%M').time(),
                    'end_time': datetime.strptime(et, '%H:%M').time(),
                    'slot_duration_minutes': settings_row.slot_duration_minutes,
                    'is_active': True,
                }
            )
        replace_weekly_availability(request.user, rows)
        messages.success(request, 'Weekly availability updated.')
        return redirect('appointments_settings')

    page_header = build_page_header(
        title='Availability settings',
        subtitle='Weekly hours, slot duration, and public profile text',
        actions=[build_button('Back to appointments', href=reverse('appointments_dashboard'), variant='secondary')],
    )
    day_labels = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    by_day = {a.day_of_week: a for a in availabilities}
    week_rows = [{'index': i, 'label': day_labels[i], 'row': by_day.get(i)} for i in range(7)]
    return render(
        request,
        'appointments/settings.html',
        {
            'page_header': page_header,
            'form': form,
            'week_rows': week_rows,
        },
    )


@appointments_manage_required
def calendar_view(request):
    qs = appointments_for_user(request.user, request).filter(
        appointment_date__gte=timezone.localdate() - timedelta(days=30),
    )
    page_header = build_page_header(
        title='Appointment calendar',
        subtitle='Upcoming and recent appointments',
        actions=[build_button('Table view', href=reverse('appointments_dashboard'), variant='secondary')],
    )
    return render(request, 'appointments/calendar.html', {'page_header': page_header, 'appointments': qs[:500]})


@appointments_manage_required
def detail(request, pk):
    appt = get_object_or_404(appointments_for_user(request.user, request), pk=pk)
    page_header = build_page_header(
        title=appt.title,
        subtitle=appt.reference_id,
        actions=[build_button('Back', href=reverse('appointments_dashboard'), variant='secondary')],
    )
    return render(request, 'appointments/detail.html', {'page_header': page_header, 'appointment': appt})


@appointments_manage_required
@require_POST
def approve(request, pk):
    appt = get_object_or_404(appointments_for_user(request.user, request), pk=pk)
    try:
        set_appointment_status(appt, request.user, Appointment.STATUS_APPROVED)
        messages.success(request, 'Appointment approved.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('appointments_dashboard')


@appointments_manage_required
@require_POST
def reject(request, pk):
    appt = get_object_or_404(appointments_for_user(request.user, request), pk=pk)
    reason = (request.POST.get('reason') or '').strip()
    set_appointment_status(appt, request.user, Appointment.STATUS_REJECTED, reason=reason)
    messages.info(request, 'Appointment rejected.')
    return redirect('appointments_dashboard')


@appointments_manage_required
@require_POST
def cancel(request, pk):
    appt = get_object_or_404(appointments_for_user(request.user, request), pk=pk)
    set_appointment_status(appt, request.user, Appointment.STATUS_CANCELLED)
    messages.info(request, 'Appointment cancelled.')
    return redirect('appointments_dashboard')


@appointments_manage_required
@require_POST
def toggle_public_link(request):
    profile = request.user.profile
    profile.is_public_booking_active = not profile.is_public_booking_active
    profile.save(update_fields=['is_public_booking_active'])
    state = 'enabled' if profile.is_public_booking_active else 'disabled'
    messages.success(request, f'Public booking link {state}.')
    return redirect('appointments_dashboard')


@appointments_manage_required
@require_POST
def regenerate_link(request):
    regenerate_booking_slug(request.user)
    messages.success(request, 'New booking link generated. Update any shared URLs.')
    return redirect('appointments_dashboard')


def public_book(request, booking_slug):
    profile = get_object_or_404(UserProfile, booking_slug=booking_slug)
    host = profile.user
    if not profile.is_public_booking_active:
        return render(request, 'appointments/public_disabled.html', {'host_name': host.get_full_name() or host.username})

    settings_row = get_or_create_settings(host)
    display_name = settings_row.public_display_name or host.get_full_name() or host.username

    selected_date = request.GET.get('date') or request.POST.get('appointment_date')
    slots = []
    if selected_date:
        try:
            from datetime import datetime

            d = datetime.strptime(selected_date, '%Y-%m-%d').date()
            slots = generate_slots_for_date(host, d, settings=settings_row)
        except ValueError:
            slots = []

    form = PublicBookingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            appt = create_public_request(host, form.cleaned_data)
            return render(
                request,
                'appointments/public_confirm.html',
                {'reference': appt.reference_id, 'host_name': display_name},
            )
        except ValueError as exc:
            messages.error(request, str(exc))

    return render(
        request,
        'appointments/public_book.html',
        {
            'host_name': display_name,
            'designation': settings_row.public_designation,
            'description': settings_row.public_description,
            'form': form,
            'slots': slots,
            'selected_date': selected_date or '',
            'min_date': timezone.localdate().isoformat(),
        },
    )


@require_GET
def public_slots_json(request, booking_slug):
    profile = get_object_or_404(UserProfile, booking_slug=booking_slug)
    if not profile.is_public_booking_active:
        return JsonResponse({'slots': []})
    date_str = request.GET.get('date', '')
    try:
        from datetime import datetime

        d = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'slots': []})
    slots = generate_slots_for_date(profile.user, d)
    return JsonResponse({'slots': slots})
