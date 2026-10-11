from django.apps import AppConfig


class IntegrationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'integration'
    verbose_name = 'Інтеграція з Matching Service'

    def ready(self):
        from . import signals  # noqa: F401  — підключає обробники сигналів
