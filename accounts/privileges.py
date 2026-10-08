from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import RolePrivilege, UserPrivilege, UserProfile, ensure_default_privileges


def get_user_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser or user.is_staff:
        return UserProfile.ROLE_ADMIN
    profile = getattr(user, 'profile', None)
    if profile is None:
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': UserProfile.ROLE_OWNER},
        )
    return profile.role


def is_admin_user(user):
    return user.is_authenticated and (
        user.is_superuser or user.is_staff or get_user_role(user) == UserProfile.ROLE_ADMIN
    )


def _role_has_privilege(role, code):
    ensure_default_privileges()
    priv = RolePrivilege.objects.filter(role=role, code=code).first()
    if priv is None:
        return False
    return priv.enabled


def has_privilege(user, code):
    if not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    role = get_user_role(user)
    if role not in (
        UserProfile.ROLE_OWNER,
        UserProfile.ROLE_TENANT,
        UserProfile.ROLE_MANAGER,
        UserProfile.ROLE_EMPLOYEE,
    ):
        return False
    override = UserPrivilege.objects.filter(user=user, code=code).first()
    if override is not None:
        return override.enabled
    return _role_has_privilege(role, code)


def list_privilege_codes_for_user(user):
    """Privilege codes currently enabled for this user (role defaults + per-user overrides)."""
    if not user.is_authenticated:
        return []
    if is_admin_user(user):
        ensure_default_privileges()
        return list(RolePrivilege.objects.values_list('code', flat=True).distinct())
    role = get_user_role(user)
    if role not in (
        UserProfile.ROLE_OWNER,
        UserProfile.ROLE_TENANT,
        UserProfile.ROLE_MANAGER,
        UserProfile.ROLE_EMPLOYEE,
    ):
        return []
    ensure_default_privileges()
    role_privs = RolePrivilege.objects.filter(role=role)
    overrides = {
        row.code: row.enabled
        for row in UserPrivilege.objects.filter(user=user, code__in=role_privs.values('code'))
    }
    enabled_codes = []
    for priv in role_privs:
        if overrides.get(priv.code, priv.enabled):
            enabled_codes.append(priv.code)
    return enabled_codes


def privilege_required(code, redirect_to='public_listings'):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not has_privilege(request.user, code):
                messages.error(request, 'You do not have permission for that action.')
                role = get_user_role(request.user)
                if role == UserProfile.ROLE_TENANT:
                    return redirect('tenant_portal')
                if role == UserProfile.ROLE_OWNER:
                    return redirect('dashboard')
                return redirect(redirect_to)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def home_for_user(user):
    if is_admin_user(user):
        return 'staff_dashboard'
    role = get_user_role(user)
    if role == UserProfile.ROLE_TENANT:
        return 'tenant_portal'
    if role in (UserProfile.ROLE_MANAGER, UserProfile.ROLE_EMPLOYEE):
        return 'hrms_dashboard'
    if role == UserProfile.ROLE_OWNER:
        try:
            from hrms.services.scoping import hrms_enabled_for_owner

            if hrms_enabled_for_owner(user) and not _owner_has_property_focus(user):
                # Prefer HRMS home when enabled; still allow property dashboard via nav
                return 'hrms_dashboard'
        except Exception:
            pass
    return 'dashboard'


def _owner_has_property_focus(user):
    """If owner already has properties, keep landing on property dashboard."""
    try:
        from properties.models import Property

        return Property.objects.filter(owner=user).exists()
    except Exception:
        return True
