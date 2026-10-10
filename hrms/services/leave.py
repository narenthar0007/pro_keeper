"""Leave types, allocations, requests, and balance calculations."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from accounts.privileges import get_user_role, has_privilege, is_admin_user
from accounts.models import UserProfile

from hrms.models import (
    Attendance,
    CompanyHoliday,
    Employee,
    EmployeeLeaveAllocation,
    LeaveAllocationAuditLog,
    LeaveAuditLog,
    LeaveRequest,
    LeaveType,
    OwnerHrmsSettings,
)
from hrms.services.scoping import employees_for_user, get_owner_for_user


def _owner_settings(owner):
    return OwnerHrmsSettings.objects.filter(owner=owner).first()


def weekly_off_set(owner) -> set[int]:
    settings_row = _owner_settings(owner)
    raw = (settings_row.weekly_off_days if settings_row else '6') or '6'
    out = set()
    for part in raw.split(','):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out or {6}


def _holiday_dates(owner, start: date, end: date) -> set[date]:
    dates = set()
    holidays = CompanyHoliday.objects.filter(owner=owner)
    for h in holidays:
        if h.recurring_annual:
            for year in range(start.year, end.year + 1):
                try:
                    d = date(year, h.date.month, h.date.day)
                except ValueError:
                    continue
                if start <= d <= end:
                    dates.add(d)
        elif start <= h.date <= end:
            dates.add(h.date)
    return dates


def iter_working_days(owner, start: date, end: date):
    if start > end:
        return
    offs = weekly_off_set(owner)
    holidays = _holiday_dates(owner, start, end)
    current = start
    while current <= end:
        if current.weekday() not in offs and current not in holidays:
            yield current
        current += timedelta(days=1)


def working_days_between(owner, start: date, end: date) -> Decimal:
    return Decimal(sum(1 for _ in iter_working_days(owner, start, end)))


def compute_requested_days(employee: Employee, leave_type: LeaveType, start: date, end: date) -> Decimal:
    if leave_type.owner_id != employee.owner_id:
        raise ValidationError('Leave type does not belong to this company.')
    return working_days_between(employee.owner, start, end)


def leave_type_applies(leave_type: LeaveType, employee: Employee) -> bool:
    if not leave_type.applicable_roles.strip():
        return True
    allowed = {r.strip().lower() for r in leave_type.applicable_roles.split(',') if r.strip()}
    role = (employee.job_role or '').strip().lower()
    return not allowed or role in allowed


def _allocation_row(employee: Employee, leave_type: LeaveType, year: int):
    return EmployeeLeaveAllocation.objects.filter(
        employee=employee,
        leave_type=leave_type,
        year=year,
    ).first()


def _used_days(employee: Employee, leave_type: LeaveType, year: int) -> Decimal:
    agg = (
        LeaveRequest.objects.filter(
            employee=employee,
            leave_type=leave_type,
            status=LeaveRequest.STATUS_APPROVED,
            start_date__year=year,
        ).aggregate(total=Sum('days_requested'))
    )
    return agg['total'] or Decimal('0')


def _pending_days(employee: Employee, leave_type: LeaveType, year: int, exclude_id=None) -> Decimal:
    qs = LeaveRequest.objects.filter(
        employee=employee,
        leave_type=leave_type,
        status=LeaveRequest.STATUS_PENDING,
        start_date__year=year,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    agg = qs.aggregate(total=Sum('days_requested'))
    return agg['total'] or Decimal('0')


def get_balance_row(employee: Employee, leave_type: LeaveType, year: int, exclude_request_id=None) -> dict:
    alloc = _allocation_row(employee, leave_type, year)
    allocated = alloc.allocated_days if alloc else leave_type.annual_entitlement
    adjustment = alloc.adjustment_days if alloc else Decimal('0')
    carry = alloc.carry_forward_days if alloc else Decimal('0')
    used = _used_days(employee, leave_type, year)
    pending = _pending_days(employee, leave_type, year, exclude_id=exclude_request_id)
    entitlement = allocated + adjustment + carry
    available = entitlement - used
    return {
        'leave_type': leave_type,
        'allocation': alloc,
        'allocated': allocated,
        'adjustment': adjustment,
        'carry_forward': carry,
        'used': used,
        'pending': pending,
        'available': available,
        'entitlement': entitlement,
    }


def get_balance_summary(employee: Employee, year: int, exclude_request_id=None) -> list[dict]:
    types = LeaveType.objects.filter(owner=employee.owner, is_active=True).order_by('name')
    return [
        get_balance_row(employee, lt, year, exclude_request_id=exclude_request_id)
        for lt in types
        if leave_type_applies(lt, employee)
    ]


def _overlapping_requests(employee, start, end, exclude_id=None):
    qs = LeaveRequest.objects.filter(
        employee=employee,
        status__in=(LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED),
    ).filter(start_date__lte=end, end_date__gte=start)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs


def validate_leave_request(
    employee: Employee,
    leave_type: LeaveType,
    start: date,
    end: date,
    exclude_request_id=None,
):
    if start > end:
        raise ValidationError('Start date cannot be after end date.')
    if not leave_type.is_active:
        raise ValidationError('This leave type is not active.')
    if leave_type.owner_id != employee.owner_id:
        raise ValidationError('Invalid leave type for this employee.')
    if not leave_type_applies(leave_type, employee):
        raise ValidationError('This leave type does not apply to this employee.')
    if not employee.is_approved:
        raise ValidationError('Employee must be approved before applying for leave.')

    days = compute_requested_days(employee, leave_type, start, end)
    if days <= 0:
        raise ValidationError('No working days in the selected range (weekends/holidays excluded).')

    if _overlapping_requests(employee, start, end, exclude_id=exclude_request_id).exists():
        raise ValidationError('Overlapping leave request already exists for these dates.')

    year = start.year
    balance = get_balance_row(employee, leave_type, year, exclude_request_id=exclude_request_id)
    used = balance['used']
    pending = balance['pending']
    entitlement = balance['entitlement']
    if used + pending + days > entitlement:
        raise ValidationError(
            f'Insufficient leave balance. Available for booking: '
            f'{entitlement - used - pending} day(s); requested {days}.'
        )
    return days


def _log_leave(owner, entity_type, entity_id, action, actor, detail=''):
    LeaveAuditLog.objects.create(
        owner=owner,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor=actor,
        detail=detail,
    )


def create_leave_request(*, employee, leave_type, start, end, reason, actor):
    role = get_user_role(actor)
    if role == UserProfile.ROLE_EMPLOYEE and employee.user_id != actor.id:
        raise ValidationError('Not allowed.')
    days = validate_leave_request(employee, leave_type, start, end)
    req = LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start,
        end_date=end,
        days_requested=days,
        reason=reason or '',
        status=LeaveRequest.STATUS_PENDING,
    )
    _log_leave(employee.owner, 'leave_request', req.pk, 'created', actor, reason[:200])
    return req


def cancel_leave_request(actor, leave_request: LeaveRequest):
    if leave_request.status not in (LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED):
        raise ValidationError('Only pending or approved requests can be cancelled.')

    role = get_user_role(actor)
    employee = leave_request.employee
    if role == UserProfile.ROLE_EMPLOYEE:
        if employee.user_id != actor.id:
            raise ValidationError('Not allowed.')
        if leave_request.status != LeaveRequest.STATUS_PENDING:
            raise ValidationError('Employees can only cancel pending requests.')
    elif role == UserProfile.ROLE_MANAGER:
        if not employees_for_user(actor).filter(pk=employee.pk).exists():
            raise ValidationError('Not allowed.')
    elif not is_admin_user(actor) and role != UserProfile.ROLE_OWNER:
        raise ValidationError('Not allowed.')
    elif role == UserProfile.ROLE_OWNER and employee.owner_id != actor.id:
        raise ValidationError('Not allowed.')

    with transaction.atomic():
        if leave_request.status == LeaveRequest.STATUS_APPROVED:
            Attendance.objects.filter(leave_request=leave_request).delete()
        leave_request.status = LeaveRequest.STATUS_CANCELLED
        leave_request.save(update_fields=['status', 'updated_at'])
        _log_leave(employee.owner, 'leave_request', leave_request.pk, 'cancelled', actor)


def _sync_attendance_for_leave(leave_request: LeaveRequest):
    employee = leave_request.employee
    owner = employee.owner
    for day in iter_working_days(owner, leave_request.start_date, leave_request.end_date):
        Attendance.objects.update_or_create(
            employee=employee,
            date=day,
            defaults={
                'owner': owner,
                'brand': employee.brand,
                'site': employee.default_site,
                'status': Attendance.STATUS_LEAVE,
                'remark': f'Leave: {leave_request.leave_type.code}',
                'leave_request': leave_request,
            },
        )


def can_approve_leave(actor, leave_request: LeaveRequest, request=None) -> bool:
    if is_admin_user(actor):
        return True
    role = get_user_role(actor)
    employee = leave_request.employee
    if role == UserProfile.ROLE_OWNER:
        return employee.owner_id == actor.id and has_privilege(actor, 'hrms_leave_approve')
    if role == UserProfile.ROLE_MANAGER:
        return (
            has_privilege(actor, 'hrms_leave_approve')
            and employees_for_user(actor, request).filter(pk=employee.pk).exists()
        )
    return False


@transaction.atomic
def approve_leave_request(actor, leave_request: LeaveRequest, comment='', request=None):
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError('Request is not pending.')
    if not can_approve_leave(actor, leave_request, request):
        raise ValidationError('Not allowed to approve this request.')

    leave_request = LeaveRequest.objects.select_for_update().get(pk=leave_request.pk)
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError('Request is not pending.')

    validate_leave_request(
        leave_request.employee,
        leave_request.leave_type,
        leave_request.start_date,
        leave_request.end_date,
        exclude_request_id=leave_request.pk,
    )

    leave_request.status = LeaveRequest.STATUS_APPROVED
    leave_request.approver = actor
    leave_request.approved_at = timezone.now()
    leave_request.approver_comment = comment or ''
    leave_request.save()

    _sync_attendance_for_leave(leave_request)
    _log_leave(
        leave_request.employee.owner,
        'leave_request',
        leave_request.pk,
        'approved',
        actor,
        comment[:200],
    )
    return leave_request


@transaction.atomic
def reject_leave_request(actor, leave_request: LeaveRequest, comment: str, request=None):
    if not comment.strip():
        raise ValidationError('Rejection reason is required.')
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError('Request is not pending.')
    if not can_approve_leave(actor, leave_request, request):
        raise ValidationError('Not allowed to reject this request.')

    leave_request = LeaveRequest.objects.select_for_update().get(pk=leave_request.pk)
    leave_request.status = LeaveRequest.STATUS_REJECTED
    leave_request.approver = actor
    leave_request.approved_at = timezone.now()
    leave_request.approver_comment = comment.strip()
    leave_request.save()
    _log_leave(
        leave_request.employee.owner,
        'leave_request',
        leave_request.pk,
        'rejected',
        actor,
        comment[:200],
    )
    return leave_request


@transaction.atomic
def upsert_allocation(
    *,
    actor,
    employee: Employee,
    leave_type: LeaveType,
    year: int,
    allocated_days,
    adjustment_days=None,
    carry_forward_days=None,
    note='',
    request=None,
):
    role = get_user_role(actor)
    if is_admin_user(actor):
        pass
    elif role == UserProfile.ROLE_OWNER:
        if employee.owner_id != actor.id or not has_privilege(actor, 'hrms_leave_allocate'):
            raise ValidationError('Not allowed.')
    elif role == UserProfile.ROLE_MANAGER:
        if not has_privilege(actor, 'hrms_leave_allocate'):
            raise ValidationError('Not allowed.')
        if not employees_for_user(actor, request).filter(pk=employee.pk).exists():
            raise ValidationError('Not allowed for this employee.')
    else:
        raise ValidationError('Not allowed.')

    if leave_type.owner_id != employee.owner_id:
        raise ValidationError('Leave type does not match employee company.')

    alloc, created = EmployeeLeaveAllocation.objects.select_for_update().get_or_create(
        employee=employee,
        leave_type=leave_type,
        year=year,
        defaults={
            'allocated_days': allocated_days,
            'adjustment_days': adjustment_days or Decimal('0'),
            'carry_forward_days': carry_forward_days or Decimal('0'),
        },
    )
    snapshot_before = {
        'allocated': str(alloc.allocated_days),
        'adjustment': str(alloc.adjustment_days),
        'carry_forward': str(alloc.carry_forward_days),
    }
    if not created:
        alloc.allocated_days = allocated_days
        if adjustment_days is not None:
            alloc.adjustment_days = adjustment_days
        if carry_forward_days is not None:
            alloc.carry_forward_days = carry_forward_days
        alloc.save()

    LeaveAllocationAuditLog.objects.create(
        allocation=alloc,
        actor=actor,
        action='created' if created else 'updated',
        note=note[:500],
        snapshot={
            'before': snapshot_before,
            'after': {
                'allocated': str(alloc.allocated_days),
                'adjustment': str(alloc.adjustment_days),
                'carry_forward': str(alloc.carry_forward_days),
            },
        },
    )
    return alloc


def seed_default_leave_types(owner, brand=None):
    defaults = [
        ('CL', 'Casual Leave', Decimal('15'), '#0b5fff'),
        ('PL', 'Privilege Leave', Decimal('10'), '#12b886'),
        ('ML', 'Medical Leave', Decimal('5'), '#e03131'),
    ]
    for code, name, ent, color in defaults:
        LeaveType.objects.get_or_create(
            owner=owner,
            code=code,
            defaults={
                'name': name,
                'annual_entitlement': ent,
                'color': color,
                'brand': brand,
                'is_paid': True,
                'is_active': True,
            },
        )


def ensure_year_allocations_from_defaults(employee: Employee, year: int):
    """Create allocation rows from leave type defaults if missing."""
    for lt in LeaveType.objects.filter(owner=employee.owner, is_active=True):
        EmployeeLeaveAllocation.objects.get_or_create(
            employee=employee,
            leave_type=lt,
            year=year,
            defaults={'allocated_days': lt.annual_entitlement},
        )
