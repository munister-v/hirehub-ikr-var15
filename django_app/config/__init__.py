# завантажуємо Celery разом із Django, щоб @shared_task знаходили додаток
from .celery import app as celery_app

__all__ = ('celery_app',)
