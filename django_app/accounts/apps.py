from django.apps import AppConfig, apps
from django.db.models.signals import post_migrate


def _create_groups(sender, **kwargs):
    from django.contrib.auth.management import create_permissions

    from .roles import ensure_groups
    # дозволи застосунку jobs мають існувати до призначення групам
    create_permissions(apps.get_app_config('jobs'), verbosity=0)
    ensure_groups()


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Акаунти та ролі'

    def ready(self):
        # post_migrate надсилається лише застосункам із моделями; в accounts їх немає,
        # тому підписуємося від імені jobs (його дозволи нам і потрібні)
        post_migrate.connect(_create_groups, sender=apps.get_app_config('jobs'),
                             dispatch_uid='accounts.create_role_groups')
