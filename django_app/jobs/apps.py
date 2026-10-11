from django.apps import AppConfig


class JobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jobs'
    verbose_name = 'Вакансії та заявки'

    def ready(self):
        from . import signals  # noqa: F401
