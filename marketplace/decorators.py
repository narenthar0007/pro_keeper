from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from accounts.privileges import has_privilege, is_admin_user


def marketplace_manage_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if is_admin_user(request.user) or has_privilege(request.user, 'marketplace_manage'):
            return view_func(request, *args, **kwargs)
        messages.error(request, 'You do not have permission to manage marketplace listings.')
        return redirect('marketplace_browse')
    return _wrapped
