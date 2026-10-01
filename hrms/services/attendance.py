"""Attendance punch / mark / regularize business rules."""

from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import UserProfile
from accounts.privileges import get_user_role, is_admin_user

from hrms.models import Attendance, Employee
from hrms.services.punch_codes import generate_punch_code
from hrms.services.scoping import employees_for_user
from hrms.services.whatsapp import punch_whatsapp_link


def _now():
    return timezone.localtime()


def _working_hours(punch_in: time, punch_out: time) -> Decimal:
    start = datetime.combine(datetime.today(), punch_in)
    end = datetime.combine(datetime.today(), punch_out)
    seconds = (end - start).total_seconds()
    if seconds < 0:
        seconds += 24 * 3600
    return Decimal(str(round(seconds / 3600.0, 2)))


def _assert_can_punch(employee: Employee):
    if not employee.can_punch:
        raise ValidationError('Employee must be Approved and Active to punch.')


def punch(*, user, punch_type: str, lat, lng, site=None, request=None):
    punch_type = (punch_type or '').lower()
    if punch_type not in ('in', 'out'):
        raise ValidationError('Punch type must be in or out.')

    employee = Employee.objects.filter(user=user).first()
    if employee is None:
        raise ValidationError('No employee profile linked to this login.')
    _assert_can_punch(employee)

    # Linked employee login may punch; owners use mark_attendance instead
    role = get_user_role(user)
    if employee.user_id == user.id:
        pass
    elif is_admin_user(user):
        pass
    elif role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_OWNER) and employees_for_user(
        user, request
    ).filter(pk=employee.pk).exists():
        pass
    else:
        raise ValidationError('Not allowed.')

    today = timezone.localdate()
    now = _now()
    owner = employee.owner

    with transaction.atomic():
        attendance, _created = Attendance.objects.get_or_create(
            employee=employee,
            date=today,
            defaults={
                'owner': owner,
                'brand': employee.brand,
                'site': site or employee.default_site,
                'project': (site or employee.default_site).name if (site or employee.default_site) else '',
                'company_name': employee.company_name,
                'marked_by': user,
            },
        )
        if punch_type == 'in':
            if attendance.punch_in:
                raise ValidationError('Already punched in today.')
            code = generate_punch_code(
                emp_code=employee.emp_code,
                name=employee.name,
                lat=lat,
                lng=lng,
                when=now,
                punch_type='in',
            )
            attendance.punch_in = now.time().replace(microsecond=0)
            attendance.lat_in = lat
            attendance.long_in = lng
            attendance.punch_code_in = code
            attendance.status = Attendance.STATUS_PRESENT
            attendance.marked_by = user
            if site:
                attendance.site = site
                attendance.project = site.name
            attendance.save()
            label = 'Punch In'
        else:
            if not attendance.punch_in:
                raise ValidationError('Punch in first.')
            if attendance.punch_out:
                raise ValidationError('Already punched out today.')
            code = generate_punch_code(
                emp_code=employee.emp_code,
                name=employee.name,
                lat=lat,
                lng=lng,
                when=now,
                punch_type='out',
            )
            attendance.punch_out = now.time().replace(microsecond=0)
            attendance.lat_out = lat
            attendance.long_out = lng
            attendance.punch_code_out = code
            attendance.working_hours = _working_hours(attendance.punch_in, attendance.punch_out)
            attendance.marked_by = user
            attendance.save()
            label = 'Punch Out'

    wa_link, wa_warn = punch_whatsapp_link(
        owner=owner,
        punch_label=label,
        attendance=attendance,
        employee=employee,
    )
    return attendance, wa_link, wa_warn


def mark_attendance(*, actor, employee, date, data: dict, request=None):
    """Owner/admin/manager mark or upsert attendance for an approved employee."""
    if not employee.can_punch and data.get('status') not in (
        Attendance.STATUS_ABSENT,
        Attendance.STATUS_LEAVE,
    ):
        # Allow absent/leave even if not punchable? Plan says cannot mark until approved.
        if not employee.is_approved:
            raise ValidationError('Cannot mark attendance until employee is Approved.')

    if not employees_for_user(actor, request).filter(pk=employee.pk).exists() and not is_admin_user(actor):
        raise ValidationError('Not allowed.')

    role = get_user_role(actor)
    if role not in (UserProfile.ROLE_OWNER, UserProfile.ROLE_MANAGER) and not is_admin_user(actor):
        raise ValidationError('Only owner or manager can mark attendance.')

    attendance, _ = Attendance.objects.update_or_create(
        employee=employee,
        date=date,
        defaults={
            'owner': employee.owner,
            'brand': employee.brand,
            'marked_by': actor,
            **{k: v for k, v in data.items() if v is not None},
        },
    )
    return attendance


def apply_regularize(*, actor, employee, date, reason: str, request=None):
    role = get_user_role(actor)
    if role == UserProfile.ROLE_EMPLOYEE:
        if not Employee.objects.filter(user=actor, pk=employee.pk).exists():
            raise ValidationError('Employees can only regularize themselves.')
    elif role == UserProfile.ROLE_MANAGER:
        if not employees_for_user(actor, request).filter(pk=employee.pk).exists():
            raise ValidationError('Not allowed for this employee.')
    elif not is_admin_user(actor) and role != UserProfile.ROLE_OWNER:
        raise ValidationError('Not allowed.')

    if not employee.is_approved:
        raise ValidationError('Employee must be Approved before regularize.')

    attendance, _ = Attendance.objects.get_or_create(
        employee=employee,
        date=date,
        defaults={
            'owner': employee.owner,
            'brand': employee.brand,
            'site': employee.default_site,
            'status': Attendance.STATUS_PRESENT,
            'marked_by': actor,
        },
    )
    attendance.regularized = Attendance.REG_YES
    attendance.approval_status = Attendance.APPROVAL_PENDING
    attendance.remark = reason
    attendance.marked_by = actor
    attendance.save()
    return attendance


def decide_regularize(*, actor, attendance: Attendance, approve: bool):
    role = get_user_role(actor)
    if not is_admin_user(actor) and role != UserProfile.ROLE_OWNER:
        raise ValidationError('Only owner or admin can approve regularize.')
    if role == UserProfile.ROLE_OWNER and attendance.owner_id != actor.id:
        raise ValidationError('Not your employee attendance.')
    if attendance.approval_status != Attendance.APPROVAL_PENDING:
        raise ValidationError('No pending regularize request.')
    attendance.approval_status = (
        Attendance.APPROVAL_APPROVED if approve else Attendance.APPROVAL_REJECTED
    )
    attendance.save(update_fields=['approval_status', 'updated_at'])
    return attendance


def approve_employee(*, actor, employee: Employee, approve: bool):
    role = get_user_role(actor)
    if not is_admin_user(actor) and role != UserProfile.ROLE_OWNER:
        raise ValidationError('Only owner or admin can approve employees.')
    if role == UserProfile.ROLE_OWNER and employee.owner_id != actor.id:
        raise ValidationError('Not your employee.')
    employee.approval_status = (
        Employee.APPROVAL_APPROVED if approve else Employee.APPROVAL_REJECTED
    )
    employee.save(update_fields=['approval_status', 'updated_at'])
    return employee
