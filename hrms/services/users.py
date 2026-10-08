"""Create / update employee and manager login users."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db import transaction

from accounts.models import UserProfile

from hrms.models import Employee


def default_password_for_mobile(mobile: str) -> str:
    digits = ''.join(c for c in (mobile or '') if c.isdigit())
    if len(digits) >= 4:
        return digits[-4:]
    return 'emp123'


def ensure_employee_login(
    employee: Employee,
    *,
    role: str,
    brand=None,
    username: str | None = None,
    password: str | None = None,
    created_by=None,
) -> User:
    """Create or update the User linked to this Employee."""
    if role not in (UserProfile.ROLE_EMPLOYEE, UserProfile.ROLE_MANAGER):
        raise ValueError('Login role must be employee or manager.')

    pwd = password or default_password_for_mobile(employee.mobile)
    username_base = f'{employee.emp_code}'.lower().replace(' ', '_')
    username_base = ''.join(c for c in username_base if c.isalnum() or c in '._')[:40] or f'emp{employee.pk}'

    with transaction.atomic():
        if employee.user_id:
            user = employee.user
            new_username = (username or '').strip()
            if new_username and new_username != user.username:
                if User.objects.filter(username=new_username).exclude(pk=user.pk).exists():
                    raise ValueError('Username already exists.')
                user.username = new_username
                user.save(update_fields=['username'])
            if password:
                user.set_password(password)
                user.save(update_fields=['password'])
        else:
            if (username or '').strip():
                login_name = username.strip()[:150]
            else:
                login_name = username_base
            n = 1
            while User.objects.filter(username=login_name).exists():
                login_name = f'{chosen}{n}'
                n += 1
            user = User.objects.create_user(
                username=login_name,
                email=employee.email or '',
                password=pwd,
            )
            employee.user = user
            employee.save(update_fields=['user'])

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        if created_by is not None:
            profile.created_by = created_by
        if brand is not None:
            profile.brand = brand
        elif employee.brand_id:
            profile.brand = employee.brand
        profile.save()
        User.objects.filter(pk=user.pk).update(is_staff=False, is_superuser=False)
        # Avoid stale reverse-relation cache (signal may have cached owner profile)
        if hasattr(user, '_state'):
            user.refresh_from_db()
        try:
            del user.profile
        except AttributeError:
            pass
        user = User.objects.get(pk=user.pk)
    return user
