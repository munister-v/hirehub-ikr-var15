"""Фонові та періодичні завдання застосунку jobs (Celery beat)."""
import logging

from celery import shared_task

from .models import Vacancy

logger = logging.getLogger(__name__)


def close_expired() -> int:
    """Закриває відкриті вакансії, термін прийому заявок яких минув. Повертає кількість."""
    expired = Vacancy.objects.expired()
    ids = list(expired.values_list('pk', flat=True))
    # витягуємо ids заздалегідь і оновлюємо поштучно, щоб спрацювали сигнали (інтеграція, кеш)
    for vacancy in Vacancy.objects.filter(pk__in=ids):
        vacancy.status = Vacancy.Status.CLOSED
        vacancy.save(update_fields=['status', 'updated'])
    logger.info('Закрито прострочених вакансій: %s', len(ids))
    return len(ids)


@shared_task(name='jobs.tasks.close_expired_vacancies')
def close_expired_vacancies():
    return close_expired()
