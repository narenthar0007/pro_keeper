"""Who may use the appointment module."""

from accounts.models import UserProfile
from accounts.privileges import get_user_role, has_privilege, is_admin_user


def user_can_manage_appointments(user):
    if not user or not user.is_authenticated:
        return False
    if is_admin_user(user):
        return True
    if has_privilege(user, 'appointments_manage'):
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.can_manage_appointments)


def appointments_for_user(user, request=None):
    from accounts.brand_scoping import get_request_brand
    from appointments.models import Appointment
    from hrms.services.scoping import get_owner_for_user

    qs = Appointment.objects.all()
    if is_admin_user(user):
        brand = get_request_brand(request) if request else None
        if brand:
            qs = qs.filter(brand=brand)
        return qs
    role = get_user_role(user)
    if role == UserProfile.ROLE_OWNER:
        return qs.filter(owner=user)
    owner = get_owner_for_user(user)
    if owner is None:
        return qs.filter(host=user)
    return qs.filter(host=user, owner=owner)
