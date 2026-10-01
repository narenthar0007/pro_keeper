"""Create in-app notifications for owners and tenants."""

from .models import UserNotification


def notify_user(*, user, brand, kind, title, url=''):
    if user is None or brand is None:
        return None
    return UserNotification.objects.create(
        user=user,
        brand=brand,
        kind=kind,
        title=title[:200],
        url=(url or '')[:400],
    )
