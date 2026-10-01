from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _setup_admin_extras(sender, **kwargs):
    if sender.name != 'accounts':
        return
    from .admin_groups import ensure_admin_groups

    ensure_admin_groups()


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'

    def ready(self):
        from . import signals  # noqa: F401
        from .admin_site import patch_admin_site

        patch_admin_site()
        post_migrate.connect(_setup_admin_extras, dispatch_uid='accounts_admin_groups')
