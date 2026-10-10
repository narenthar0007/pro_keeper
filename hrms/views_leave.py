"""HRMS leave management, approvals, and calendar views."""

from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.brand_scoping import get_request_brand
from accounts.models import UserProfile
from accounts.privileges import get_user_role, has_privilege, is_admin_user
from accounts.ui_components import build_button, build_kpis, build_page_header
from accounts.ui_table import build_table

from hrms.decorators import hrms_login_required
from hrms.forms import (
    CompanyHolidayForm,
    LeaveAllocationForm,
    LeaveApplyForm,
    LeaveDecisionForm,
    LeaveTypeForm,
)
from hrms.models import Attendance, CompanyHoliday, Employee, LeaveRequest, LeaveType
from hrms.services.calendar_grid import build_month_weeks
from hrms.services.leave import (
    approve_leave_request,
    cancel_leave_request,
    create_leave_request,
    get_balance_summary,
    reject_leave_request,
    seed_default_leave_types,
    upsert_allocation,
    working_days_between,
)
from hrms.services.scoping import (
    attendance_for_user,
    employees_for_user,
    get_owner_for_user,
    holidays_for_user,
    leave_requests_for_user,
    leave_types_for_user,
)


def _redirect_hrms():
    return redirect('hrms_dashboard')


def _require_priv(request, code):
    if not has_privilege(request.user, code):
        messages.error(request, 'You do not have permission for that action.')
        return _redirect_hrms()
    return None


def _owner_user(request):
    role = get_user_role(request.user)
    if role == UserProfile.ROLE_OWNER:
        return request.user
    if is_admin_user(request.user):
        return None
    return get_owner_for_user(request.user)


@hrms_login_required
def leave_type_list(request):
    if _require_priv(request, 'hrms_manage_leave'):
        return _redirect_hrms()
    owner = request.user if get_user_role(request.user) == UserProfile.ROLE_OWNER else None
    if owner is None and not is_admin_user(request.user):
        return _redirect_hrms()
    brand = get_request_brand(request)
    if owner:
        seed_default_leave_types(owner, brand)
    qs = leave_types_for_user(request.user, request)
    if owner:
        qs = qs.filter(owner=owner)
    rows = [
        {
            'name': lt.name,
            'code': lt.code,
            'entitlement': str(lt.annual_entitlement),
            'paid': 'Yes' if lt.is_paid else 'No',
            'active': 'Active' if lt.is_active else 'Inactive',
            'actions': (
                f'<a href="{reverse("hrms_leave_type_edit", args=[lt.pk])}">Edit</a>'
            ),
        }
        for lt in qs
    ]
    table = build_table(
        id='leave-types',
        columns=[
            {'key': 'name', 'label': 'Name'},
            {'key': 'code', 'label': 'Code'},
            {'key': 'entitlement', 'label': 'Default days/yr'},
            {'key': 'paid', 'label': 'Paid'},
            {'key': 'active', 'label': 'Status', 'badge': True},
            {'key': 'actions', 'label': '', 'html': True},
        ],
        rows=rows,
        empty_text='No leave types yet.',
    )
    page_header = build_page_header(
        title='Leave types',
        subtitle='Configure leave categories and calendar colors',
        actions=[
            build_button('Add leave type', href=reverse('hrms_leave_type_create'), variant='primary'),
            build_button('Company holidays', href=reverse('hrms_holidays'), variant='secondary'),
        ],
    )
    return render(request, 'hrms/list_page.html', {'page_header': page_header, 'table': table, 'kpis': None})


@hrms_login_required
def leave_type_create(request):
    if _require_priv(request, 'hrms_manage_leave'):
        return _redirect_hrms()
    owner = request.user
    brand = get_request_brand(request)
    if request.method == 'POST':
        form = LeaveTypeForm(request.POST)
        if form.is_valid():
            lt = form.save(commit=False)
            lt.owner = owner
            lt.brand = brand
            lt.save()
            messages.success(request, 'Leave type created.')
            return redirect('hrms_leave_types')
    else:
        form = LeaveTypeForm()
    return render(
        request,
        'hrms/form_page.html',
        {'page_header': build_page_header('Add leave type'), 'form': form},
    )


@hrms_login_required
def leave_type_edit(request, pk):
    if _require_priv(request, 'hrms_manage_leave'):
        return _redirect_hrms()
    lt = get_object_or_404(leave_types_for_user(request.user, request), pk=pk, owner=request.user)
    if request.method == 'POST':
        form = LeaveTypeForm(request.POST, instance=lt)
        if form.is_valid():
            form.save()
            messages.success(request, 'Leave type updated.')
            return redirect('hrms_leave_types')
    else:
        form = LeaveTypeForm(instance=lt)
    return render(
        request,
        'hrms/form_page.html',
        {
            'page_header': build_page_header(f'Edit {lt.name}'),
            'form': form,
        },
    )


@hrms_login_required
def holiday_list(request):
    if _require_priv(request, 'hrms_manage_leave'):
        return _redirect_hrms()
    year = int(request.GET.get('year', timezone.localdate().year))
    qs = holidays_for_user(request.user, request).filter(date__year=year)
    rows = [
        {
            'name': h.name,
            'date': h.date.strftime('%d %b %Y'),
            'recurring': 'Yes' if h.recurring_annual else 'No',
            'actions': f'<a href="{reverse("hrms_holiday_edit", args=[h.pk])}">Edit</a>',
        }
        for h in qs
    ]
    table = build_table(
        id='holidays',
        columns=[
            {'key': 'name', 'label': 'Holiday'},
            {'key': 'date', 'label': 'Date'},
            {'key': 'recurring', 'label': 'Annual'},
            {'key': 'actions', 'label': '', 'html': True},
        ],
        rows=rows,
        empty_text='No holidays for this year.',
    )
    page_header = build_page_header(
        title='Company holidays',
        subtitle=f'Year {year}',
        actions=[build_button('Add holiday', href=reverse('hrms_holiday_create'), variant='primary')],
    )
    return render(
        request,
        'hrms/list_page.html',
        {'page_header': page_header, 'table': table, 'kpis': None, 'filter_year': year},
    )


@hrms_login_required
def holiday_create(request):
    if _require_priv(request, 'hrms_manage_leave'):
        return _redirect_hrms()
    brand = get_request_brand(request)
    if request.method == 'POST':
        form = CompanyHolidayForm(request.POST)
        if form.is_valid():
            h = form.save(commit=False)
            h.owner = request.user
            h.brand = brand
            if not h.color:
                from hrms.services.scoping import get_or_create_owner_settings

                settings_row = get_or_create_owner_settings(request.user, brand)
                h.color = settings_row.holiday_calendar_color or '#9333ea'
            h.save()
            messages.success(request, 'Holiday saved.')
            return redirect('hrms_holidays')
    else:
        form = CompanyHolidayForm()
    return render(
        request,
        'hrms/form_page.html',
        {'page_header': build_page_header('Add company holiday'), 'form': form},
    )


@hrms_login_required
def holiday_edit(request, pk):
    if _require_priv(request, 'hrms_manage_leave'):
        return _redirect_hrms()
    h = get_object_or_404(holidays_for_user(request.user, request), pk=pk, owner=request.user)
    if request.method == 'POST':
        form = CompanyHolidayForm(request.POST, instance=h)
        if form.is_valid():
            form.save()
            messages.success(request, 'Holiday updated.')
            return redirect('hrms_holidays')
    else:
        form = CompanyHolidayForm(instance=h)
    return render(
        request,
        'hrms/form_page.html',
        {'page_header': build_page_header(f'Edit {h.name}'), 'form': form},
    )


@hrms_login_required
def leave_allocation_list(request):
    if _require_priv(request, 'hrms_leave_allocate'):
        return _redirect_hrms()
    year = int(request.GET.get('year', timezone.localdate().year))
    employee_id = request.GET.get('employee')
    emps = employees_for_user(request.user, request).filter(approval_status=Employee.APPROVAL_APPROVED)
    employee = None
    balances = []
    if employee_id:
        employee = get_object_or_404(emps, pk=employee_id)
        balances = get_balance_summary(employee, year)
    rows = []
    for row in balances:
        lt = row['leave_type']
        rows.append(
            {
                'type': lt.name,
                'allocated': str(row['allocated']),
                'used': str(row['used']),
                'pending': str(row['pending']),
                'available': str(row['available']),
            }
        )
    table = build_table(
        id='leave-alloc',
        columns=[
            {'key': 'type', 'label': 'Leave type'},
            {'key': 'allocated', 'label': 'Allocated'},
            {'key': 'used', 'label': 'Used'},
            {'key': 'pending', 'label': 'Pending'},
            {'key': 'available', 'label': 'Available'},
        ],
        rows=rows,
        empty_text='Select an employee to view balances.',
    )
    page_header = build_page_header(
        title='Leave allocations',
        subtitle=f'Year {year}',
        actions=[
            build_button('Assign / adjust', href=reverse('hrms_leave_allocation_edit'), variant='primary'),
        ],
    )
    return render(
        request,
        'hrms/leave_allocations.html',
        {
            'page_header': page_header,
            'employees': emps,
            'selected_employee': employee,
            'year': year,
            'table': table,
        },
    )


@hrms_login_required
def leave_allocation_edit(request):
    if _require_priv(request, 'hrms_leave_allocate'):
        return _redirect_hrms()
    emps = employees_for_user(request.user, request).filter(approval_status=Employee.APPROVAL_APPROVED)
    types_qs = leave_types_for_user(request.user, request).filter(is_active=True)
    if request.method == 'POST':
        form = LeaveAllocationForm(request.POST, employees_qs=emps, types_qs=types_qs)
        if form.is_valid():
            try:
                upsert_allocation(
                    actor=request.user,
                    employee=form.cleaned_data['employee'],
                    leave_type=form.cleaned_data['leave_type'],
                    year=form.cleaned_data['year'],
                    allocated_days=form.cleaned_data['allocated_days'],
                    adjustment_days=form.cleaned_data.get('adjustment_days'),
                    carry_forward_days=form.cleaned_data.get('carry_forward_days'),
                    note=form.cleaned_data.get('note') or '',
                    request=request,
                )
                messages.success(request, 'Allocation saved.')
                emp = form.cleaned_data['employee']
                return redirect(f'{reverse("hrms_leave_allocations")}?employee={emp.pk}&year={form.cleaned_data["year"]}')
            except ValidationError as exc:
                messages.error(request, str(exc))
    else:
        form = LeaveAllocationForm(employees_qs=emps, types_qs=types_qs)
    return render(
        request,
        'hrms/form_page.html',
        {'page_header': build_page_header('Assign leave balance'), 'form': form},
    )


@hrms_login_required
def leave_my(request):
    if _require_priv(request, 'hrms_leave_apply'):
        return _redirect_hrms()
    employee = Employee.objects.filter(user=request.user).first()
    if not employee:
        messages.error(request, 'No employee profile linked to your login.')
        return _redirect_hrms()
    year = int(request.GET.get('year', timezone.localdate().year))
    balances = get_balance_summary(employee, year)
    history = leave_requests_for_user(request.user, request).filter(employee=employee)[:50]
    bal_rows = [
        {
            'type': row['leave_type'].name,
            'allocated': str(row['entitlement']),
            'used': str(row['used']),
            'pending': str(row['pending']),
            'available': str(row['available']),
        }
        for row in balances
    ]
    bal_table = build_table(
        id='my-leave-bal',
        columns=[
            {'key': 'type', 'label': 'Leave type'},
            {'key': 'allocated', 'label': 'Entitlement'},
            {'key': 'used', 'label': 'Used'},
            {'key': 'pending', 'label': 'Pending'},
            {'key': 'available', 'label': 'Available'},
        ],
        rows=bal_rows,
        empty_text='No leave types configured.',
    )
    hist_table = build_table(
        id='my-leave-hist',
        columns=[
            {'key': 'dates', 'label': 'Dates'},
            {'key': 'type', 'label': 'Type'},
            {'key': 'days', 'label': 'Days'},
            {'key': 'status', 'label': 'Status', 'badge': True},
            {'key': 'comment', 'label': 'Approver note'},
        ],
        rows=[
            {
                'dates': f'{r.start_date} – {r.end_date}',
                'type': r.leave_type.name,
                'days': str(r.days_requested),
                'status': r.status,
                'comment': r.approver_comment or '—',
            }
            for r in history
        ],
        empty_text='No leave requests yet.',
    )
    page_header = build_page_header(
        title='My leaves',
        subtitle=f'Year {year}',
        actions=[build_button('Apply for leave', href=reverse('hrms_leave_apply'), variant='primary')],
    )
    return render(
        request,
        'hrms/leave_my.html',
        {
            'page_header': page_header,
            'bal_table': bal_table,
            'hist_table': hist_table,
            'history': history,
            'year': year,
        },
    )


@hrms_login_required
def leave_apply(request):
    if _require_priv(request, 'hrms_leave_apply'):
        return _redirect_hrms()
    employee = Employee.objects.filter(user=request.user).first()
    if not employee:
        messages.error(request, 'No employee profile linked.')
        return _redirect_hrms()
    types_qs = leave_types_for_user(request.user, request).filter(is_active=True, owner=employee.owner)
    preview_days = None
    if request.method == 'POST':
        form = LeaveApplyForm(request.POST, employee=employee, types_qs=types_qs)
        if form.is_valid():
            try:
                create_leave_request(
                    employee=employee,
                    leave_type=form.cleaned_data['leave_type'],
                    start=form.cleaned_data['start_date'],
                    end=form.cleaned_data['end_date'],
                    reason=form.cleaned_data['reason'],
                    actor=request.user,
                )
                messages.success(request, 'Leave request submitted.')
                return redirect('hrms_leave_my')
            except ValidationError as exc:
                messages.error(request, str(exc))
        else:
            if form.cleaned_data.get('leave_type') and form.cleaned_data.get('start_date') and form.cleaned_data.get('end_date'):
                try:
                    preview_days = working_days_between(
                        employee.owner,
                        form.cleaned_data['start_date'],
                        form.cleaned_data['end_date'],
                    )
                except Exception:
                    preview_days = None
    else:
        form = LeaveApplyForm(employee=employee, types_qs=types_qs)
    return render(
        request,
        'hrms/form_page.html',
        {
            'page_header': build_page_header(
                'Apply for leave',
                subtitle=f'Working days preview: {preview_days}' if preview_days is not None else '',
            ),
            'form': form,
        },
    )


@hrms_login_required
@require_POST
def leave_cancel(request, pk):
    req = get_object_or_404(leave_requests_for_user(request.user, request), pk=pk)
    try:
        cancel_leave_request(request.user, req)
        messages.success(request, 'Leave request cancelled.')
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('hrms_leave_my')


@hrms_login_required
def leave_requests(request):
    if _require_priv(request, 'hrms_leave_approve'):
        return _redirect_hrms()
    status = request.GET.get('status', LeaveRequest.STATUS_PENDING)
    qs = leave_requests_for_user(request.user, request)
    if status:
        qs = qs.filter(status=status)
    employee_id = request.GET.get('employee')
    if employee_id:
        qs = qs.filter(employee_id=employee_id)
    leave_type_id = request.GET.get('leave_type')
    if leave_type_id:
        qs = qs.filter(leave_type_id=leave_type_id)
    rows = []
    for r in qs[:100]:
        bal = get_balance_summary(r.employee, r.start_date.year)
        avail = next((b['available'] for b in bal if b['leave_type'].pk == r.leave_type_id), '—')
        rows.append(
            {
                'employee': r.employee.name,
                'type': r.leave_type.name,
                'dates': f'{r.start_date} – {r.end_date}',
                'days': str(r.days_requested),
                'available': str(avail),
                'reason': (r.reason[:80] + '…') if len(r.reason) > 80 else r.reason,
                'status': r.status,
                'actions': (
                    f'<a href="{reverse("hrms_leave_request_detail", args=[r.pk])}">Review</a>'
                    if r.status == LeaveRequest.STATUS_PENDING
                    else '—'
                ),
            }
        )
    table = build_table(
        id='leave-reqs',
        columns=[
            {'key': 'employee', 'label': 'Employee'},
            {'key': 'type', 'label': 'Leave type'},
            {'key': 'dates', 'label': 'Dates'},
            {'key': 'days', 'label': 'Days'},
            {'key': 'available', 'label': 'Available'},
            {'key': 'reason', 'label': 'Reason'},
            {'key': 'status', 'label': 'Status', 'badge': True},
            {'key': 'actions', 'label': '', 'html': True},
        ],
        rows=rows,
        empty_text='No leave requests match filters.',
    )
    page_header = build_page_header(title='Leave requests', subtitle=f'Status: {status}')
    return render(
        request,
        'hrms/list_page.html',
        {
            'page_header': page_header,
            'table': table,
            'kpis': None,
            'status_filter': status,
            'employees': employees_for_user(request.user, request),
            'leave_types': leave_types_for_user(request.user, request).filter(is_active=True),
        },
    )


@hrms_login_required
def leave_request_detail(request, pk):
    if _require_priv(request, 'hrms_leave_approve'):
        return _redirect_hrms()
    req = get_object_or_404(leave_requests_for_user(request.user, request), pk=pk)
    if request.method == 'POST':
        form = LeaveDecisionForm(request.POST)
        if form.is_valid():
            try:
                if form.cleaned_data['action'] == 'approve':
                    approve_leave_request(
                        request.user,
                        req,
                        comment=form.cleaned_data.get('comment') or '',
                        request=request,
                    )
                    messages.success(request, 'Leave approved.')
                else:
                    reject_leave_request(
                        request.user,
                        req,
                        comment=form.cleaned_data['comment'],
                        request=request,
                    )
                    messages.success(request, 'Leave rejected.')
                return redirect('hrms_leave_requests')
            except ValidationError as exc:
                messages.error(request, str(exc))
    else:
        form = LeaveDecisionForm()
    balances = get_balance_summary(req.employee, req.start_date.year)
    return render(
        request,
        'hrms/leave_request_detail.html',
        {
            'page_header': build_page_header(
                f'Leave request — {req.employee.name}',
                subtitle=f'{req.leave_type.name} · {req.status}',
            ),
            'leave_request': req,
            'form': form,
            'balances': balances,
        },
    )


@hrms_login_required
def hrms_calendar(request):
    if _require_priv(request, 'hrms_leave_calendar'):
        return _redirect_hrms()
    today = timezone.localdate()
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    role = get_user_role(request.user)
    emps = employees_for_user(request.user, request).filter(approval_status=Employee.APPROVAL_APPROVED)
    employee = None
    employee_id = request.GET.get('employee')
    if role == UserProfile.ROLE_EMPLOYEE:
        employee = Employee.objects.filter(user=request.user).first()
    elif employee_id:
        employee = emps.filter(pk=employee_id).first()
    elif emps.exists():
        employee = emps.first()

    show_attendance = request.GET.get('show_attendance', '1') != '0'
    show_holidays = request.GET.get('show_holidays', '1') != '0'
    leave_type_filter = request.GET.get('leave_type')

    events_by_day = {}
    legend = []

    if employee:
        owner = employee.owner
        grid = build_month_weeks(year, month, today, events_by_day)
        start, end = grid['start'], grid['end']

        if show_holidays:
            from hrms.services.leave import _holiday_dates
            from hrms.services.scoping import get_or_create_owner_settings

            settings_row = get_or_create_owner_settings(owner)
            hcolor = settings_row.holiday_calendar_color or '#9333ea'
            for hdate in sorted(_holiday_dates(owner, start, end)):
                if hdate.month != month:
                    continue
                events_by_day.setdefault(hdate.day, []).append(
                    {
                        'label': 'Holiday',
                        'color': hcolor,
                        'pending': False,
                        'title': 'Company holiday',
                    }
                )
            legend.append({'label': 'Holiday', 'color': hcolor, 'pending': False})

        reqs = LeaveRequest.objects.filter(
            employee=employee,
            start_date__lte=end,
            end_date__gte=start,
        ).select_related('leave_type')
        if leave_type_filter:
            reqs = reqs.filter(leave_type_id=leave_type_filter)
        for req in reqs:
            if req.status == LeaveRequest.STATUS_CANCELLED:
                continue
            pending = req.status == LeaveRequest.STATUS_PENDING
            color = req.leave_type.color
            current = max(req.start_date, start)
            while current <= min(req.end_date, end):
                if current.month == month:
                    events_by_day.setdefault(current.day, []).append(
                        {
                            'label': req.leave_type.code,
                            'color': color,
                            'pending': pending,
                            'title': f'{req.leave_type.name} ({req.status})',
                        }
                    )
                current += timedelta(days=1)
            if req.leave_type.code not in [x['label'] for x in legend if not x.get('pending')]:
                legend.append(
                    {
                        'label': req.leave_type.name,
                        'color': color,
                        'pending': pending,
                    }
                )

        if show_attendance:
            att_qs = attendance_for_user(request.user, request).filter(
                employee=employee,
                date__gte=start,
                date__lte=end,
            )
            for att in att_qs:
                if att.date.month != month:
                    continue
                label = att.status
                color = '#64748b'
                if att.status == Attendance.STATUS_PRESENT:
                    color = '#12b886'
                elif att.status == Attendance.STATUS_ABSENT:
                    color = '#e03131'
                elif att.status == Attendance.STATUS_LEAVE:
                    color = '#fab005'
                events_by_day.setdefault(att.date.day, []).append(
                    {
                        'label': label,
                        'color': color,
                        'pending': False,
                        'title': f'Attendance: {att.status}',
                    }
                )
            legend.append({'label': 'Attendance', 'color': '#64748b', 'pending': False})

        grid = build_month_weeks(year, month, today, events_by_day)
    else:
        grid = build_month_weeks(year, month, today, {})

    page_header = build_page_header(
        title='HRMS calendar',
        subtitle=employee.name if employee else 'Select an employee',
    )
    return render(
        request,
        'hrms/calendar.html',
        {
            'page_header': page_header,
            'weeks': grid['weeks'],
            'month_label': grid['month_label'],
            'prev': grid['prev'],
            'next': grid['next'],
            'year': year,
            'month': month,
            'employees': emps,
            'selected_employee': employee,
            'legend': legend,
            'leave_types': leave_types_for_user(request.user, request).filter(is_active=True),
            'show_attendance': show_attendance,
            'show_holidays': show_holidays,
        },
    )
