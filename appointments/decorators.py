from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from appointments.services.access import user_can_manage_appointments


def appointments_manage_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not user_can_manage_appointments(request.user):
            messages.error(request, 'You do not have permission to manage appointments.')
            try:
                from accounts.privileges import home_for_user

                return redirect(home_for_user(request.user))
            except Exception:
                return redirect('public_listings')
        return view_func(request, *args, **kwargs)

    return _wrapped
