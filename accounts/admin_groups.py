"""Default Django auth groups for admin roles."""

from django.contrib.auth.models import Group, Permission


def ensure_admin_groups():
    """Finance viewer: changelist + export only (no edits)."""
    group, created = Group.objects.get_or_create(name='Finance viewer')
    if created or group.permissions.count() == 0:
        view_perms = Permission.objects.filter(
            codename__startswith='view_',
            content_type__app_label__in=('properties', 'accounts'),
        ).exclude(codename='view_logentry')
        group.permissions.set(view_perms)
