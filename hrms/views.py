import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.brand_scoping import get_request_brand
from accounts.models import UserProfile
from accounts.privileges import get_user_role, is_admin_user
from accounts.ui_components import (
    build_button,
    build_empty,
    build_kpis,
    build_page_header,
)
from accounts.ui_table import build_table

from hrms.decorators import hrms_login_required, owner_or_admin_required
from hrms.forms import (
    AdminOwnerHrmsEnableForm,
    AttendanceMarkForm,
    EmployeeForm,
    ManagerCreateForm,
    MaterialForm,
    OwnerHrmsSettingsForm,
    PunchDecodeForm,
    PunchForm,
    RegularizeForm,
    SiteAssignForm,
    SiteDailyUpdateForm,
    SiteForm,
)
from hrms.models import (
    Attendance,
    Employee,
    OwnerHrmsSettings,
    Site,
    SiteAssignment,
    SiteDailyUpdate,
)
from hrms.services.attendance import (
    apply_regularize,
    approve_employee,
    decide_regularize,
    mark_attendance,
    punch,
)
from hrms.services.punch_codes import decode_punch_code
from hrms.services.scoping import (
    attendance_for_user,
    employees_for_user,
    get_or_create_owner_settings,
    get_owner_for_user,
    site_updates_for_user,
    sites_for_user,
    user_can_access_hrms,
)
from hrms.services.users import ensure_employee_login


def _sync_employee_login_from_form(form, employee, *, brand, created_by):
    """Create, update, or remove login based on Can login fields."""
    if form.cleaned_data.get('can_login'):
        try:
            return ensure_employee_login(
                employee,
                role=UserProfile.ROLE_EMPLOYEE,
                brand=brand,
                created_by=created_by,
                username=(form.cleaned_data.get('login_username') or '').strip() or None,
                password=form.cleaned_data.get('login_password') or None,
            )
        except ValueError as exc:
            raise ValidationError(str(exc))
    if employee.user_id:
        user = employee.user
        employee.user = None
        employee.save(update_fields=['user'])
        user.is_active = False
        user.save(update_fields=['is_active'])
    return None


def _properties_qs(owner):
    try:
        from properties.models import Property

        return Property.objects.filter(owner=owner)
    except Exception:
        return []


@hrms_login_required
def hrms_dashboard(request):
    employees = employees_for_user(request.user, request)
    attendance = attendance_for_user(request.user, request)
    sites = sites_for_user(request.user, request)
    today = timezone.localdate()
    emp_stats = employees.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(approval_status=Employee.APPROVAL_PENDING)),
    )
    att_stats = attendance.aggregate(
        pending_reg=Count('pk', filter=Q(approval_status=Attendance.APPROVAL_PENDING)),
        present_today=Count(
            'pk',
            filter=Q(date=today, status=Attendance.STATUS_PRESENT),
        ),
    )
    site_count = sites.count()

    kpis = build_kpis(
        [
            {'label': 'Employees', 'value': emp_stats['total']},
            {'label': 'Sites', 'value': site_count},
            {'label': 'Present today', 'value': att_stats['present_today']},
            {
                'label': 'Pending approvals',
                'value': emp_stats['pending'] + att_stats['pending_reg'],
                'tone': 'warn',
            },
        ]
    )
    page_header = build_page_header(
        title='HRMS Dashboard',
        subtitle='Attendance, sites, and workforce for your company',
        actions=[
            build_button('Employees', href=reverse('hrms_employees'), variant='secondary'),
            build_button('Punch', href=reverse('hrms_punch'), variant='primary'),
        ],
    )
    recent = attendance.order_by('-date', '-id')[:10]
    table = build_table(
        id='hrms-recent-att',
        columns=[
            {'key': 'date', 'label': 'Date'},
            {'key': 'employee', 'label': 'Employee'},
            {'key': 'status', 'label': 'Status', 'badge': True},
            {'key': 'in', 'label': 'In'},
            {'key': 'out', 'label': 'Out'},
        ],
        rows=[
            {
                'date': a.date.strftime('%d %b %Y'),
                'employee': a.employee.name,
                'status': a.status,
                'in': a.punch_in.strftime('%H:%M') if a.punch_in else '—',
                'out': a.punch_out.strftime('%H:%M') if a.punch_out else '—',
            }
            for a in recent
        ],
        empty_text='No attendance yet.',
    )
    return render(
        request,
        'hrms/dashboard.html',
        {
            'page_header': page_header,
            'kpis': kpis,
            'table': table,
            'role': get_user_role(request.user),
        },
    )


@hrms_login_required
def employee_list(request):
    qs = employees_for_user(request.user, request)
    role = get_user_role(request.user)
    status_filter = request.GET.get('approval', '').strip()
    if status_filter:
        qs = qs.filter(approval_status=status_filter)

    show_punch_columns = role == UserProfile.ROLE_MANAGER
    today = timezone.localdate()
    stats = qs.aggregate(
        total=Count('pk'),
        pending=Count('pk', filter=Q(approval_status=Employee.APPROVAL_PENDING)),
        approved=Count('pk', filter=Q(approval_status=Employee.APPROVAL_APPROVED)),
    )
    employee_list = list(qs)
    subtitle = f'{stats["total"]} people in scope'
    if show_punch_columns:
        subtitle += f' · Punch in/out for {today.strftime("%d %b %Y")}'

    actions = []
    if role in (UserProfile.ROLE_OWNER,) or is_admin_user(request.user):
        actions.append(build_button('Add employee', href=reverse('hrms_employee_create'), variant='primary'))
        actions.append(build_button('Add manager', href=reverse('hrms_manager_create'), variant='secondary'))

    page_header = build_page_header(
        title='Employees',
        subtitle=subtitle,
        actions=actions,
    )
    kpis = build_kpis(
        [
            {'label': 'Total', 'value': stats['total']},
            {'label': 'Pending', 'value': stats['pending'], 'tone': 'warn'},
            {'label': 'Approved', 'value': stats['approved']},
        ]
    )
    attendance_today = {}
    if show_punch_columns and employee_list:
        employee_ids = [e.pk for e in employee_list]
        attendance_today = {
            row.employee_id: row
            for row in attendance_for_user(request.user, request).filter(
                date=today,
                employee_id__in=employee_ids,
            )
        }

    rows = []
    for e in employee_list:
        att = attendance_today.get(e.pk) if show_punch_columns else None
        punch_in = att.punch_in.strftime('%H:%M') if att and att.punch_in else '—'
        punch_out = att.punch_out.strftime('%H:%M') if att and att.punch_out else '—'
        row_data = {
            'code': e.emp_code,
            'name': e.name,
            'mobile': e.mobile,
            'site': e.default_site.name if e.default_site_id else '—',
            'approval': e.approval_status,
            'status': e.status,
            'login': e.user.username if e.user_id else '—',
            'actions': (
                f'<a href="{reverse("hrms_employee_edit", args=[e.pk])}">Edit</a>'
            ),
        }
        if show_punch_columns:
            row_data['punch_in'] = punch_in
            row_data['punch_out'] = punch_out
        rows.append(row_data)

    columns = [
        {'key': 'code', 'label': 'Code'},
        {'key': 'name', 'label': 'Name'},
        {'key': 'mobile', 'label': 'Mobile'},
        {'key': 'site', 'label': 'Site'},
        {'key': 'approval', 'label': 'Approval', 'badge': True},
        {'key': 'status', 'label': 'Status', 'badge': True},
        {'key': 'login', 'label': 'Login'},
    ]
    if show_punch_columns:
        columns.extend(
            [
                {'key': 'punch_in', 'label': 'Punch in'},
                {'key': 'punch_out', 'label': 'Punch out'},
            ]
        )
    columns.append({'key': 'actions', 'label': '', 'html': True})

    table = build_table(
        id='hrms-employees',
        columns=columns,
        rows=rows,
        empty_text='No employees yet.',
    )
    return render(
        request,
        'hrms/list_page.html',
        {'page_header': page_header, 'kpis': kpis, 'table': table},
    )


@hrms_login_required
def employee_create(request):
    role = get_user_role(request.user)
    if role not in (UserProfile.ROLE_OWNER, UserProfile.ROLE_MANAGER) and not is_admin_user(request.user):
        messages.error(request, 'Not allowed.')
        return redirect('hrms_employees')

    if role == UserProfile.ROLE_OWNER:
        owner = request.user
    else:
        owner = get_owner_for_user(request.user)
    if owner is None:
        messages.error(request, 'Could not resolve company owner.')
        return redirect('hrms_employees')

    sites = sites_for_user(request.user, request)
    brand = get_request_brand(request)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, owner=owner, sites_qs=sites)
        if form.is_valid():
            emp = form.save(commit=False)
            emp.owner = owner
            emp.brand = brand
            emp.created_by = request.user
            emp.approval_status = Employee.APPROVAL_PENDING
            emp.save()
            login_user = None
            try:
                login_user = _sync_employee_login_from_form(
                    form, emp, brand=brand, created_by=request.user
                )
            except ValidationError as exc:
                messages.error(request, str(exc))
                return render(
                    request,
                    'hrms/form_page.html',
                    {'page_header': build_page_header(title='Add employee'), 'form': form},
                )
            msg = f'Employee {emp.emp_code} created (Pending approval).'
            if login_user:
                msg += f' Login username: {login_user.username}. They can sign in after approval.'
            messages.success(request, msg)
            return redirect('hrms_employees')
    else:
        form = EmployeeForm(owner=owner, sites_qs=sites)

    page_header = build_page_header(
        title='Add employee',
        subtitle='Starts as Pending until owner approves. Enable Can login to set username and password.',
    )
    return render(request, 'hrms/form_page.html', {'page_header': page_header, 'form': form})


@hrms_login_required
def employee_edit(request, pk):
    emp = get_object_or_404(employees_for_user(request.user, request), pk=pk)
    sites = sites_for_user(request.user, request)
    role = get_user_role(request.user)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=emp, owner=emp.owner, sites_qs=sites)
        if form.is_valid():
            emp = form.save()
            brand = get_request_brand(request)
            try:
                login_user = _sync_employee_login_from_form(
                    form, emp, brand=brand, created_by=request.user
                )
            except ValidationError as exc:
                messages.error(request, str(exc))
                return redirect('hrms_employee_edit', pk=emp.pk)
            msg = 'Employee updated.'
            if login_user:
                msg += f' Login: {login_user.username}.'
            messages.success(request, msg)
            return redirect('hrms_employees')
    else:
        form = EmployeeForm(instance=emp, owner=emp.owner, sites_qs=sites)

    actions = []
    if (role == UserProfile.ROLE_OWNER or is_admin_user(request.user)) and emp.approval_status == Employee.APPROVAL_PENDING:
        actions.append(
            build_button('Approve', href=reverse('hrms_employee_approve', args=[emp.pk]), variant='primary')
        )
        actions.append(
            build_button('Reject', href=reverse('hrms_employee_reject', args=[emp.pk]), variant='danger')
        )
    page_header = build_page_header(
        title=f'{emp.name} ({emp.emp_code})',
        subtitle=f'Approval: {emp.approval_status}',
        actions=actions,
    )
    return render(request, 'hrms/form_page.html', {'page_header': page_header, 'form': form, 'employee': emp})


@hrms_login_required
@require_POST
def employee_approve(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    try:
        approve_employee(actor=request.user, employee=emp, approve=True)
        messages.success(request, f'{emp.name} approved.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
    return redirect('hrms_employees')


@hrms_login_required
@require_POST
def employee_reject(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    try:
        approve_employee(actor=request.user, employee=emp, approve=False)
        messages.success(request, f'{emp.name} rejected.')
    except ValidationError as exc:
        messages.error(request, '; '.join(exc.messages) if hasattr(exc, 'messages') else str(exc))
    return redirect('hrms_employees')


# GET approve/reject buttons from edit page — allow GET for simplicity with confirm
@hrms_login_required
def employee_approve_get(request, pk):
    if request.method != 'POST':
        # Convert link clicks to POST-like via form page; still enforce owner
        emp = get_object_or_404(Employee, pk=pk)
        try:
            approve_employee(actor=request.user, employee=emp, approve=True)
            messages.success(request, f'{emp.name} approved.')
        except ValidationError as exc:
            messages.error(request, str(exc))
        return redirect('hrms_employees')
    return employee_approve(request, pk)


@hrms_login_required
def employee_reject_get(request, pk):
    emp = get_object_or_404(Employee, pk=pk)
    try:
        approve_employee(actor=request.user, employee=emp, approve=False)
        messages.success(request, f'{emp.name} rejected.')
    except ValidationError as exc:
        messages.error(request, str(exc))
    return redirect('hrms_employees')


@hrms_login_required
@owner_or_admin_required
def manager_create(request):
    owner = request.user if get_user_role(request.user) == UserProfile.ROLE_OWNER else None
    if owner is None and is_admin_user(request.user):
        messages.error(request, 'Create managers while logged in as the company owner.')
        return redirect('hrms_employees')

    brand = get_request_brand(request)
    if request.method == 'POST':
        form = ManagerCreateForm(request.POST, owner=owner)
        if form.is_valid():
            data = form.cleaned_data
            if Employee.objects.filter(owner=owner, emp_code=data['emp_code']).exists():
                form.add_error('emp_code', 'Code already used.')
            elif Employee.objects.filter(owner=owner, mobile=data['mobile']).exists():
                form.add_error('mobile', 'Mobile already used.')
            else:
                emp = Employee.objects.create(
                    owner=owner,
                    brand=brand,
                    emp_code=data['emp_code'],
                    name=data['name'],
                    mobile=data['mobile'],
                    email=data.get('email') or '',
                    latitude=data['latitude'],
                    longitude=data['longitude'],
                    default_site=data.get('default_site'),
                    approval_status=Employee.APPROVAL_APPROVED,
                    created_by=request.user,
                    company_name=owner.username,
                )
                user = ensure_employee_login(
                    emp,
                    role=UserProfile.ROLE_MANAGER,
                    brand=brand,
                    username=data.get('username') or None,
                    password=data.get('password') or None,
                    created_by=request.user,
                )
                site = data.get('default_site')
                if site:
                    SiteAssignment.objects.get_or_create(site=site, manager=user)
                messages.success(request, f'Manager {user.username} created.')
                return redirect('hrms_employees')
    else:
        form = ManagerCreateForm(owner=owner)

    page_header = build_page_header(
        title='Add manager',
        subtitle='Manager is approved by default and can be assigned to sites',
    )
    return render(request, 'hrms/form_page.html', {'page_header': page_header, 'form': form})


@hrms_login_required
def site_list(request):
    qs = sites_for_user(request.user, request)
    role = get_user_role(request.user)
    actions = []
    if role == UserProfile.ROLE_OWNER or is_admin_user(request.user):
        actions.append(build_button('Add site', href=reverse('hrms_site_create'), variant='primary'))
    page_header = build_page_header(title='Sites / Projects', subtitle=f'{qs.count()} sites', actions=actions)
    rows = []
    for s in qs:
        managers = ', '.join(a.manager.username for a in s.assignments.select_related('manager'))
        rows.append(
            {
                'name': s.name,
                'type': s.get_site_type_display(),
                'status': s.status,
                'managers': managers or '—',
                'actions': f'<a href="{reverse("hrms_site_detail", args=[s.pk])}">Open</a>',
            }
        )
    table = build_table(
        id='hrms-sites',
        columns=[
            {'key': 'name', 'label': 'Name'},
            {'key': 'type', 'label': 'Type'},
            {'key': 'status', 'label': 'Status', 'badge': True},
            {'key': 'managers', 'label': 'Managers'},
            {'key': 'actions', 'label': '', 'html': True},
        ],
        rows=rows,
        empty_text='No sites yet.',
    )
    return render(request, 'hrms/list_page.html', {'page_header': page_header, 'table': table, 'kpis': None})


@hrms_login_required
@owner_or_admin_required
def site_create(request):
    owner = request.user
    brand = get_request_brand(request)
    props = _properties_qs(owner)
    if request.method == 'POST':
        form = SiteForm(request.POST, properties_qs=props)
        if form.is_valid():
            site = form.save(commit=False)
            site.owner = owner
            site.brand = brand
            site.created_by = request.user
            site.save()
            messages.success(request, 'Site created.')
            return redirect('hrms_site_detail', pk=site.pk)
    else:
        form = SiteForm(properties_qs=props)
    page_header = build_page_header(title='Add site', subtitle='Project, home, renovation, or construction')
    return render(request, 'hrms/form_page.html', {'page_header': page_header, 'form': form})


@hrms_login_required
def site_detail(request, pk):
    site = get_object_or_404(sites_for_user(request.user, request), pk=pk)
    role = get_user_role(request.user)
    assign_form = None
    if role == UserProfile.ROLE_OWNER or is_admin_user(request.user):
        managers = UserProfile.objects.filter(
            role=UserProfile.ROLE_MANAGER,
            user__hrms_employee__owner=site.owner,
        ).select_related('user')
        managers_qs = [p.user for p in managers]
        from django.contrib.auth.models import User

        mq = User.objects.filter(id__in=[u.id for u in managers_qs])
        if request.method == 'POST' and request.POST.get('action') == 'assign':
            assign_form = SiteAssignForm(request.POST, managers_qs=mq)
            if assign_form.is_valid():
                SiteAssignment.objects.get_or_create(
                    site=site,
                    manager=assign_form.cleaned_data['manager'],
                )
                messages.success(request, 'Manager assigned.')
                return redirect('hrms_site_detail', pk=site.pk)
        else:
            assign_form = SiteAssignForm(managers_qs=mq)

    page_header = build_page_header(
        title=site.name,
        subtitle=f'{site.get_site_type_display()} · {site.status}',
        actions=[
            build_button('Post update', href=reverse('hrms_update_create') + f'?site={site.pk}', variant='primary'),
        ],
    )
    assignments = site.assignments.select_related('manager')
    return render(
        request,
        'hrms/site_detail.html',
        {
            'page_header': page_header,
            'site': site,
            'assignments': assignments,
            'assign_form': assign_form,
        },
    )


@hrms_login_required
def attendance_list(request):
    qs = attendance_for_user(request.user, request).order_by('-date', '-id')
    role = get_user_role(request.user)
    is_employee = role == UserProfile.ROLE_EMPLOYEE
    att_total = qs.count()
    actions = []
    if role in (UserProfile.ROLE_EMPLOYEE, UserProfile.ROLE_MANAGER) or is_admin_user(request.user):
        actions.append(build_button('Punch', href=reverse('hrms_punch'), variant='primary'))
    if role in (UserProfile.ROLE_OWNER, UserProfile.ROLE_MANAGER) or is_admin_user(request.user):
        actions.append(build_button('Mark attendance', href=reverse('hrms_attendance_mark'), variant='secondary'))
    if is_employee or role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_OWNER) or is_admin_user(request.user):
        actions.append(build_button('Regularize', href=reverse('hrms_regularize'), variant='secondary'))
    if not is_employee:
        actions.append(build_button('Export CSV', href=reverse('hrms_attendance_export'), variant='secondary'))

    title = 'My attendance' if is_employee else 'Attendance'
    subtitle = f'{att_total} records' if not is_employee else f'{att_total} of your records'
    page_header = build_page_header(title=title, subtitle=subtitle, actions=actions)
    rows = []
    for a in qs[:100]:
        row = {
            'date': a.date.strftime('%d %b %Y'),
            'status': a.status,
            'in': a.punch_in.strftime('%H:%M') if a.punch_in else '—',
            'out': a.punch_out.strftime('%H:%M') if a.punch_out else '—',
            'hours': str(a.working_hours) if a.working_hours is not None else '—',
            'reg': a.regularized,
            'approval': a.approval_status,
        }
        if not is_employee:
            row['employee'] = a.employee.name
        rows.append(row)

    columns = [{'key': 'date', 'label': 'Date'}]
    if not is_employee:
        columns.append({'key': 'employee', 'label': 'Employee'})
    columns.extend(
        [
            {'key': 'status', 'label': 'Status', 'badge': True},
            {'key': 'in', 'label': 'In'},
            {'key': 'out', 'label': 'Out'},
            {'key': 'hours', 'label': 'Hours'},
            {'key': 'reg', 'label': 'Regularized'},
            {'key': 'approval', 'label': 'Reg. approval', 'badge': True},
        ]
    )
    table = build_table(
        id='hrms-attendance',
        columns=columns,
        rows=rows,
        empty_text='No attendance records yet.',
    )
    return render(request, 'hrms/list_page.html', {'page_header': page_header, 'table': table, 'kpis': None})


@hrms_login_required
def attendance_mark(request):
    role = get_user_role(request.user)
    if role not in (UserProfile.ROLE_OWNER, UserProfile.ROLE_MANAGER) and not is_admin_user(request.user):
        messages.error(request, 'Not allowed.')
        return redirect('hrms_attendance')
    emps = employees_for_user(request.user, request).filter(approval_status=Employee.APPROVAL_APPROVED)
    sites = sites_for_user(request.user, request)
    if request.method == 'POST':
        form = AttendanceMarkForm(request.POST, employees_qs=emps, sites_qs=sites)
        if form.is_valid():
            try:
                mark_attendance(
                    actor=request.user,
                    employee=form.cleaned_data['employee'],
                    date=form.cleaned_data['date'],
                    data={
                        'punch_in': form.cleaned_data.get('punch_in'),
                        'punch_out': form.cleaned_data.get('punch_out'),
                        'shift': form.cleaned_data.get('shift'),
                        'status': form.cleaned_data.get('status'),
                        'site': form.cleaned_data.get('site'),
                        'remark': form.cleaned_data.get('remark') or '',
                        'overtime': form.cleaned_data.get('overtime'),
                    },
                    request=request,
                )
                messages.success(request, 'Attendance saved.')
                return redirect('hrms_attendance')
            except ValidationError as exc:
                messages.error(request, str(exc))
    else:
        form = AttendanceMarkForm(employees_qs=emps, sites_qs=sites)
    page_header = build_page_header(title='Mark attendance', subtitle='Upsert by employee + date')
    return render(request, 'hrms/form_page.html', {'page_header': page_header, 'form': form})


@hrms_login_required
def punch_view(request):
    role = get_user_role(request.user)
    if role not in (UserProfile.ROLE_EMPLOYEE, UserProfile.ROLE_MANAGER) and not is_admin_user(request.user):
        messages.info(request, 'Owners mark attendance from the Attendance page.')
        return redirect('hrms_attendance')
    sites = sites_for_user(request.user, request)
    wa_link = None
    if request.method == 'POST':
        form = PunchForm(request.POST, sites_qs=sites)
        if form.is_valid():
            try:
                att, wa_link, warn = punch(
                    user=request.user,
                    punch_type=form.cleaned_data['punch_type'],
                    lat=form.cleaned_data['latitude'],
                    lng=form.cleaned_data['longitude'],
                    site=form.cleaned_data.get('site'),
                    request=request,
                )
                messages.success(
                    request,
                    f'{form.cleaned_data["punch_type"].title()} saved. '
                    f'Code: {att.punch_code_in or att.punch_code_out}',
                )
                if warn:
                    messages.warning(request, warn)
            except ValidationError as exc:
                messages.error(request, str(exc))
    else:
        form = PunchForm(sites_qs=sites)
    page_header = build_page_header(
        title='Punch in / out',
        subtitle='Allow location access; once per day for in and out',
    )
    return render(
        request,
        'hrms/punch.html',
        {'page_header': page_header, 'form': form, 'wa_link': wa_link},
    )


@hrms_login_required
def regularize_view(request):
    role = get_user_role(request.user)
    emps = employees_for_user(request.user, request)
    if role == UserProfile.ROLE_EMPLOYEE:
        emps = emps.filter(user=request.user)
    if request.method == 'POST':
        form = RegularizeForm(request.POST, employees_qs=emps)
        if form.is_valid():
            try:
                apply_regularize(
                    actor=request.user,
                    employee=form.cleaned_data['employee'],
                    date=form.cleaned_data['date'],
                    reason=form.cleaned_data['reason'],
                    request=request,
                )
                messages.success(request, 'Regularize request submitted (Pending owner approval).')
                if role == UserProfile.ROLE_EMPLOYEE:
                    return redirect('hrms_attendance')
                return redirect('hrms_approvals')
            except ValidationError as exc:
                messages.error(request, str(exc))
    else:
        form = RegularizeForm(employees_qs=emps)
    page_header = build_page_header(title='Apply regularize', subtitle='Owner must approve')
    return render(request, 'hrms/form_page.html', {'page_header': page_header, 'form': form})


@hrms_login_required
def approvals(request):
    role = get_user_role(request.user)
    pending_emps = employees_for_user(request.user, request).filter(
        approval_status=Employee.APPROVAL_PENDING
    )
    pending_reg = attendance_for_user(request.user, request).filter(
        approval_status=Attendance.APPROVAL_PENDING
    )
    can_approve = role == UserProfile.ROLE_OWNER or is_admin_user(request.user)

    if request.method == 'POST' and can_approve:
        kind = request.POST.get('kind')
        pk = request.POST.get('pk')
        action = request.POST.get('action')
        try:
            if kind == 'employee':
                emp = get_object_or_404(Employee, pk=pk)
                approve_employee(actor=request.user, employee=emp, approve=(action == 'approve'))
                messages.success(request, 'Employee decision saved.')
            elif kind == 'regularize':
                att = get_object_or_404(Attendance, pk=pk)
                decide_regularize(actor=request.user, attendance=att, approve=(action == 'approve'))
                messages.success(request, 'Regularize decision saved.')
        except ValidationError as exc:
            messages.error(request, str(exc))
        return redirect('hrms_approvals')

    page_header = build_page_header(
        title='Approvals',
        subtitle='Employee approvals and regularize requests',
    )
    return render(
        request,
        'hrms/approvals.html',
        {
            'page_header': page_header,
            'pending_emps': pending_emps,
            'pending_reg': pending_reg,
            'can_approve': can_approve,
        },
    )


@hrms_login_required
def update_list(request):
    qs = site_updates_for_user(request.user, request)
    role = get_user_role(request.user)
    actions = []
    if role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_OWNER) or is_admin_user(request.user):
        actions.append(build_button('Post update', href=reverse('hrms_update_create'), variant='primary'))
    page_header = build_page_header(title='Site updates', subtitle='Headcount, materials, work done', actions=actions)
    rows = [
        {
            'date': u.date.strftime('%d %b %Y'),
            'site': u.site.name,
            'manager': u.manager.username,
            'present': u.employees_present_count,
            'pct': f'{u.percent_complete}%',
            'work': (u.work_done[:80] + '…') if len(u.work_done) > 80 else u.work_done,
        }
        for u in qs[:100]
    ]
    table = build_table(
        id='hrms-updates',
        columns=[
            {'key': 'date', 'label': 'Date'},
            {'key': 'site', 'label': 'Site'},
            {'key': 'manager', 'label': 'Manager'},
            {'key': 'present', 'label': 'Present'},
            {'key': 'pct', 'label': '% done'},
            {'key': 'work', 'label': 'Work done'},
        ],
        rows=rows,
        empty_text='No site updates yet.',
    )
    return render(request, 'hrms/list_page.html', {'page_header': page_header, 'table': table, 'kpis': None})


@hrms_login_required
def update_create(request):
    role = get_user_role(request.user)
    if role not in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_OWNER) and not is_admin_user(request.user):
        messages.error(request, 'Not allowed.')
        return redirect('hrms_updates')
    sites = sites_for_user(request.user, request)
    brand = get_request_brand(request)
    owner = get_owner_for_user(request.user) if role != UserProfile.ROLE_OWNER else request.user
    initial = {}
    site_id = request.GET.get('site')
    if site_id:
        initial['site'] = site_id
    if request.method == 'POST':
        form = SiteDailyUpdateForm(request.POST, sites_qs=sites)
        material_form = MaterialForm(request.POST, prefix='mat')
        if form.is_valid():
            update = form.save(commit=False)
            update.owner = owner or form.cleaned_data['site'].owner
            update.brand = brand
            update.manager = request.user
            update.save()
            if material_form.is_valid() and material_form.cleaned_data.get('item'):
                mat = material_form.save(commit=False)
                mat.update = update
                mat.save()
            messages.success(request, 'Site update posted.')
            return redirect('hrms_updates')
    else:
        form = SiteDailyUpdateForm(initial=initial, sites_qs=sites)
        material_form = MaterialForm(prefix='mat')
    page_header = build_page_header(title='Post site update', subtitle='Visible to the owner')
    return render(
        request,
        'hrms/update_form.html',
        {'page_header': page_header, 'form': form, 'material_form': material_form},
    )


@hrms_login_required
def reports(request):
    decoded = None
    form = PunchDecodeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            decoded = decode_punch_code(form.cleaned_data['code'])
        except ValueError as exc:
            form.add_error('code', str(exc))
    page_header = build_page_header(
        title='HRMS Reports',
        subtitle='Export attendance and decode punch codes',
        actions=[
            build_button('Export attendance CSV', href=reverse('hrms_attendance_export'), variant='primary'),
            build_button('Export employees CSV', href=reverse('hrms_employees_export'), variant='secondary'),
        ],
    )
    return render(
        request,
        'hrms/reports.html',
        {'page_header': page_header, 'form': form, 'decoded': decoded},
    )


@hrms_login_required
def attendance_export(request):
    qs = attendance_for_user(request.user, request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            'date',
            'employeeId',
            'name',
            'punchIn',
            'punchOut',
            'workingHours',
            'status',
            'regularized',
            'approval',
            'punchCodeIn',
            'punchCodeOut',
            'owner',
        ]
    )
    for a in qs.iterator():
        writer.writerow(
            [
                a.date,
                a.employee.emp_code,
                a.employee.name,
                a.punch_in,
                a.punch_out,
                a.working_hours,
                a.status,
                a.regularized,
                a.approval_status,
                a.punch_code_in,
                a.punch_code_out,
                a.owner.username,
            ]
        )
    return response


@hrms_login_required
def employees_export(request):
    qs = employees_for_user(request.user, request)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'
    writer = csv.writer(response)
    writer.writerow(
        ['id', 'name', 'mobile', 'status', 'approval', 'site', 'owner', 'latitude', 'longitude']
    )
    for e in qs.iterator():
        writer.writerow(
            [
                e.emp_code,
                e.name,
                e.mobile,
                e.status,
                e.approval_status,
                e.default_site.name if e.default_site_id else '',
                e.owner.username,
                e.latitude,
                e.longitude,
            ]
        )
    return response


@hrms_login_required
def hrms_settings(request):
    role = get_user_role(request.user)
    brand = get_request_brand(request)
    if is_admin_user(request.user) and role != UserProfile.ROLE_OWNER:
        from django.contrib.auth.models import User

        # Quick enable / disable from this page
        if request.method == 'POST':
            owner_id = request.POST.get('owner_id')
            action = request.POST.get('action')
            owner = get_object_or_404(User, pk=owner_id, profile__role=UserProfile.ROLE_OWNER)
            settings_row = get_or_create_owner_settings(owner, brand=brand)
            if action == 'enable':
                settings_row.hrms_enabled = True
                settings_row.save(update_fields=['hrms_enabled', 'updated_at'])
                messages.success(request, f'HRMS enabled for {owner.username}.')
            elif action == 'disable':
                settings_row.hrms_enabled = False
                settings_row.save(update_fields=['hrms_enabled', 'updated_at'])
                messages.success(request, f'HRMS disabled for {owner.username}.')
            return redirect('hrms_settings')

        owners = (
            User.objects.filter(profile__role=UserProfile.ROLE_OWNER)
            .select_related('profile')
            .order_by('username')
        )
        owner_rows = []
        for owner in owners:
            s = OwnerHrmsSettings.objects.filter(owner=owner).first()
            owner_rows.append(
                {
                    'owner': owner,
                    'settings': s,
                    'enabled': bool(s and s.hrms_enabled),
                    'industry': s.get_industry_display() if s else '—',
                    'whatsapp': (s.whatsapp_number if s else '') or '—',
                    'is_paid': bool(s and s.is_paid),
                }
            )
        page_header = build_page_header(
            title='HRMS subscriptions',
            subtitle='Enable HRMS for each owner company from this page',
        )
        return render(
            request,
            'hrms/admin_settings_list.html',
            {'page_header': page_header, 'owner_rows': owner_rows},
        )

    if role != UserProfile.ROLE_OWNER:
        messages.error(request, 'Only owners can edit HRMS settings.')
        return redirect('hrms_dashboard')

    settings_row = get_or_create_owner_settings(request.user, brand=brand)
    if request.method == 'POST':
        form = OwnerHrmsSettingsForm(request.POST, instance=settings_row)
        if form.is_valid():
            theme_fields = [
                'button_color',
                'header_color',
                'bg_color',
                'text_color',
                'sidebar_color',
                'button_style',
                'theme_preset',
            ]
            theme_changed = any(
                form.cleaned_data.get(f) != getattr(settings_row, f) for f in theme_fields
            )
            if theme_changed and settings_row.theme_locked_this_month:
                messages.error(request, 'Theme can only be changed once per calendar month.')
            else:
                obj = form.save(commit=False)
                if theme_changed:
                    obj.theme_edited_at = timezone.localdate().strftime('%Y-%m')
                obj.save()
                messages.success(request, 'Settings saved.')
                return redirect('hrms_settings')
    else:
        form = OwnerHrmsSettingsForm(instance=settings_row)

    page_header = build_page_header(
        title='HRMS settings',
        subtitle='WhatsApp alerts and theme (one theme change per month)',
    )
    return render(
        request,
        'hrms/form_page.html',
        {
            'page_header': page_header,
            'form': form,
            'extra_note': (
                f'Theme last edited: {settings_row.theme_edited_at or "never"}. '
                f'HRMS access: {"ON" if settings_row.hrms_enabled else "OFF (ask admin to enable)"}.'
            ),
        },
    )


@login_required
def admin_toggle_owner_hrms(request, owner_id):
    if not is_admin_user(request.user):
        messages.error(request, 'Admin only.')
        return redirect('hrms_dashboard')
    from django.contrib.auth.models import User

    owner = get_object_or_404(User, pk=owner_id)
    brand = get_request_brand(request)
    settings_row = get_or_create_owner_settings(owner, brand=brand)
    if request.method == 'POST':
        form = AdminOwnerHrmsEnableForm(request.POST, instance=settings_row)
        if form.is_valid():
            form.save()
            messages.success(request, f'HRMS settings updated for {owner.username}.')
            return redirect('hrms_settings')
    else:
        form = AdminOwnerHrmsEnableForm(instance=settings_row)
    page_header = build_page_header(title=f'HRMS for {owner.username}', subtitle='Subscription / enable')
    return render(request, 'hrms/form_page.html', {'page_header': page_header, 'form': form})
