"""Celery-завдання синхронізації з Matching Service. Помилки мережі не ламають збереження даних."""
import logging

from celery import shared_task
from django.conf import settings

from jobs.models import Application, Candidate, Vacancy

from .client import MatchingUnavailable, get_client
from .payloads import application_payload, candidate_payload, vacancy_payload

logger = logging.getLogger(__name__)
MAX_RETRIES = 3


def _guard(task, func):
    """Виконує func; мережеві збої повторюються з відступом (у eager-режимі — одразу пропускаються)."""
    if not settings.MATCHING_ENABLED:
        return None
    try:
        return func()
    except MatchingUnavailable as exc:
        if task.request.is_eager or task.request.retries >= MAX_RETRIES:
            logger.warning('Синхронізація пропущена: %s', exc)
            return None
        raise task.retry(exc=exc, countdown=5 * 2 ** task.request.retries)


@shared_task(bind=True, name='integration.tasks.sync_vacancy')
def sync_vacancy(self, vacancy_id):
    """Оновлює індекс: відкриті вакансії індексуються, решта — видаляються з індексу."""
    def run():
        client = get_client()
        try:
            vacancy = Vacancy.objects.with_related().get(pk=vacancy_id)
        except Vacancy.DoesNotExist:
            return client.delete_vacancy(vacancy_id)
        if not vacancy.is_open:
            return client.delete_vacancy(vacancy_id)
        return client.index_vacancy(vacancy_payload(vacancy))
    return _guard(self, run)


@shared_task(bind=True, name='integration.tasks.sync_candidate')
def sync_candidate(self, candidate_id):
    def run():
        client = get_client()
        try:
            candidate = Candidate.objects.select_related('city').prefetch_related(
                'candidate_skills__skill').get(pk=candidate_id)
        except Candidate.DoesNotExist:
            return client.delete_candidate(candidate_id)
        return client.index_candidate(candidate_payload(candidate))
    return _guard(self, run)


@shared_task(bind=True, name='integration.tasks.notify_application_status')
def notify_application_status(self, application_id):
    def run():
        application = Application.objects.select_related('vacancy').get(pk=application_id)
        return get_client().notify_application_status(application_payload(application))
    try:
        return _guard(self, run)
    except Application.DoesNotExist:
        return None


@shared_task(bind=True, name='integration.tasks.reindex_all')
def reindex_all(self):
    """Повна переіндексація: усі відкриті вакансії та всі кандидати одним пакетом."""
    def run():
        vacancies = [vacancy_payload(v) for v in Vacancy.objects.open().with_related()]
        candidates = [candidate_payload(c) for c in Candidate.objects.select_related('city').prefetch_related(
            'candidate_skills__skill')]
        return get_client().reindex(vacancies, candidates)
    return _guard(self, run)
