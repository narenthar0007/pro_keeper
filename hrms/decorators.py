"""HRMS access decorators."""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from accounts.models import UserProfile
from accounts.privileges import get_user_role, is_admin_user
from hrms.services.scoping import user_can_access_hrms


def hrms_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not user_can_access_hrms(request.user):
            messages.error(request, 'HRMS is not enabled for your account.')
            role = get_user_role(request.user)
            if role == UserProfile.ROLE_TENANT:
                return redirect('tenant_portal')
            if is_admin_user(request.user):
                return redirect('staff_dashboard')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)

    return _wrapped


def owner_or_admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        role = get_user_role(request.user)
        if not is_admin_user(request.user) and role != UserProfile.ROLE_OWNER:
            messages.error(request, 'Only owners or admins can do that.')
            return redirect('hrms_dashboard')
        return view_func(request, *args, **kwargs)

    return _wrapped
