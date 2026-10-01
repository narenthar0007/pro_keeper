from django.utils import timezone

from .brands import resolve_brand
from .logging_utils import log_activity

SKIP_PREFIXES = (
    '/static/',
    '/media/',
    '/favicon.ico',
    '/admin/jsi18n/',
)


def _guess_action(method, path):
    method = (method or '').upper()
    path = path or ''
    if path.startswith('/accounts/login'):
        return 'login'
    if path.startswith('/accounts/logout'):
        return 'logout'
    if path.startswith('/accounts/register'):
        return 'register'
    if method == 'POST' and ('/delete' in path or path.endswith('/delete/')):
        return 'delete'
    if method == 'POST' and ('/add' in path or path.endswith('/add/') or '/create' in path):
        return 'create'
    if method in {'POST', 'PUT', 'PATCH'}:
        return 'update'
    if method == 'GET':
        return 'view'
    return 'other'


class BrandMiddleware:
    """Attach request.brand from host / preview session."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            request.brand = resolve_brand(request)
        except Exception:
            request.brand = None
        return self.get_response(request)


class RentReminderMiddleware:
    """Send the monthly rent reminder email once per session-day when due."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        if not any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            user = getattr(request, 'user', None)
            if user is not None and getattr(user, 'is_authenticated', False):
                today = str(timezone.localdate())
                session = getattr(request, 'session', None)
                if session is not None and session.get('_rent_reminder_checked') != today:
                    try:
                        from .reminders import maybe_send_rent_reminder

                        maybe_send_rent_reminder(user, brand=getattr(request, 'brand', None))
                    except Exception:
                        pass
                    try:
                        session['_rent_reminder_checked'] = today
                    except Exception:
                        pass
        return self.get_response(request)


class ActivityLogMiddleware:
    """Capture page/API activity for the staff activity log."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path or ''
        if any(path.startswith(prefix) for prefix in SKIP_PREFIXES):
            return response

        # Skip noisy polling of the activity panel itself optional; still log it
        action = _guess_action(request.method, path)
        message = f'{request.method} {path} → {response.status_code}'

        log_activity(
            request=request,
            action=action,
            message=message,
            status_code=response.status_code,
        )
        return response
