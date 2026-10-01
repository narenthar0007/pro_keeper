from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .logging_utils import log_activity


@receiver(user_logged_in)
def on_user_logged_in(sender, request, user, **kwargs):
    log_activity(
        request=request,
        user=user,
        action='login',
        message=f'User {user.username} logged in',
    )


@receiver(user_logged_out)
def on_user_logged_out(sender, request, user, **kwargs):
    log_activity(
        request=request,
        user=user,
        action='logout',
        message=f'User {getattr(user, "username", "unknown")} logged out',
    )
