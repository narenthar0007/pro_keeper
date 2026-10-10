"""Role-aware queryset scoping for HRMS."""

from __future__ import annotations

from django.db.models import Q

from accounts.brand_scoping import get_request_brand
from accounts.models import UserProfile
from accounts.privileges import get_user_role, is_admin_user

from hrms.models import (
    Attendance,
    CompanyHoliday,
    Employee,
    LeaveRequest,
    LeaveType,
    OwnerHrmsSettings,
    Site,
    SiteAssignment,
    SiteDailyUpdate,
)


def get_owner_for_user(user):
    """Return the company owner User for this login, or None."""
    if not user or not user.is_authenticated:
        return None
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return user
    if role == UserProfile.ROLE_MANAGER:
        emp = getattr(user, 'hrms_employee', None)
        if emp is not None:
            return emp.owner
        # Fallback: any assignment's site owner
        assignment = SiteAssignment.objects.filter(manager=user).select_related('site').first()
        return assignment.site.owner if assignment else None
    if role == UserProfile.ROLE_EMPLOYEE:
        emp = getattr(user, 'hrms_employee', None)
        return emp.owner if emp else None
    return None


def hrms_enabled_for_owner(owner):
    if owner is None:
        return False
    settings_row = OwnerHrmsSettings.objects.filter(owner=owner).first()
    return bool(settings_row and settings_row.hrms_enabled)


def user_can_access_hrms(user):
    if not user or not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return hrms_enabled_for_owner(user)
    if role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_EMPLOYEE):
        owner = get_owner_for_user(user)
        return hrms_enabled_for_owner(owner)
    return False


def manager_site_ids(user):
    return list(
        SiteAssignment.objects.filter(manager=user).values_list('site_id', flat=True)
    )


def sites_for_user(user, request=None):
    qs = Site.objects.all()
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(brand=brand)
        return qs
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(owner=user)
    if role == UserProfile.ROLE_MANAGER:
        return qs.filter(assignments__manager=user).distinct()
    if role == UserProfile.ROLE_EMPLOYEE:
        emp = getattr(user, 'hrms_employee', None)
        if emp is not None and emp.default_site_id:
            return qs.filter(pk=emp.default_site_id)
        return qs.none()
    return qs.none()


def employees_for_user(user, request=None):
    qs = Employee.objects.select_related('default_site', 'user', 'owner')
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(brand=brand)
        return qs
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(owner=user)
    if role == UserProfile.ROLE_MANAGER:
        site_ids = manager_site_ids(user)
        return qs.filter(
            Q(owner=get_owner_for_user(user))
            & (Q(default_site_id__in=site_ids) | Q(user=user))
        ).distinct()
    if role == UserProfile.ROLE_EMPLOYEE:
        return qs.filter(user=user)
    return qs.none()


def attendance_for_user(user, request=None):
    qs = Attendance.objects.select_related('employee', 'employee__user', 'site', 'owner')
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(brand=brand)
        return qs
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(owner=user)
    if role == UserProfile.ROLE_MANAGER:
        site_ids = manager_site_ids(user)
        return qs.filter(
            Q(owner=get_owner_for_user(user))
            & (Q(site_id__in=site_ids) | Q(employee__user=user) | Q(employee__default_site_id__in=site_ids))
        ).distinct()
    if role == UserProfile.ROLE_EMPLOYEE:
        return qs.filter(employee__user=user)
    return qs.none()


def site_updates_for_user(user, request=None):
    qs = SiteDailyUpdate.objects.select_related('site', 'manager', 'owner')
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(brand=brand)
        return qs
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(owner=user)
    if role == UserProfile.ROLE_MANAGER:
        return qs.filter(manager=user)
    return qs.none()


def leave_requests_for_user(user, request=None):
    qs = LeaveRequest.objects.select_related(
        'employee',
        'leave_type',
        'approver',
    )
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(employee__brand=brand)
        return qs
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(employee__owner=user)
    if role == UserProfile.ROLE_MANAGER:
        emp_ids = employees_for_user(user, request).values('pk')
        return qs.filter(employee_id__in=emp_ids)
    if role == UserProfile.ROLE_EMPLOYEE:
        return qs.filter(employee__user=user)
    return qs.none()


def leave_types_for_user(user, request=None):
    qs = LeaveType.objects.all()
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(brand=brand)
        return qs
    role = get_user_role(user)
    owner = get_owner_for_user(user) if role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_EMPLOYEE) else None
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(owner=user)
    if owner:
        return qs.filter(owner=owner)
    return qs.none()


def holidays_for_user(user, request=None):
    qs = CompanyHoliday.objects.all()
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(brand=brand)
        return qs
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(owner=user)
    owner = get_owner_for_user(user)
    if owner:
        return qs.filter(owner=owner)
    return qs.none()


def get_or_create_owner_settings(owner, brand=None):
    defaults = {}
    if brand is not None:
        defaults['brand'] = brand
    settings_row, _ = OwnerHrmsSettings.objects.get_or_create(owner=owner, defaults=defaults)
    if brand is not None and settings_row.brand_id is None:
        settings_row.brand = brand
        settings_row.save(update_fields=['brand'])
    return settings_row
