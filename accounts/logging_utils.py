from .models import ActivityLog


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_activity(
    *,
    request=None,
    user=None,
    action='other',
    message='',
    path='',
    method='',
    status_code=None,
):
    username = ''
    if user is not None and getattr(user, 'is_authenticated', False):
        username = user.get_username()
    elif request is not None and getattr(request.user, 'is_authenticated', False):
        user = request.user
        username = request.user.get_username()
    else:
        user = None

    ip = None
    user_agent = ''
    if request is not None:
        ip = get_client_ip(request)
        user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:400]
        path = path or request.path
        method = method or request.method

    try:
        brand = None
        if request is not None:
            from .brand_scoping import get_request_brand

            brand = get_request_brand(request)
        ActivityLog.objects.create(
            user=user if user and getattr(user, 'is_authenticated', False) else None,
            username=username or 'anonymous',
            action=action,
            method=method,
            path=path[:500],
            status_code=status_code,
            ip_address=ip,
            user_agent=user_agent,
            message=message[:500],
            brand=brand,
        )
    except Exception:
        # Never break the app because logging failed
        pass
