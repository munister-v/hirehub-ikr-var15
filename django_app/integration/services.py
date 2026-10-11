"""Безпечні виклики Matching Service для веб-сторінок: при збої повертають порожній результат."""
import logging

from django.conf import settings

from .client import MatchingUnavailable, get_client

logger = logging.getLogger(__name__)


def _safe(func, default):
    if not settings.MATCHING_ENABLED:
        return default
    try:
        return func()
    except MatchingUnavailable:
        return default
    except Exception:  # noqa: BLE001 — сторінка не має падати через рекомендації
        logger.exception('Неочікувана помилка інтеграції')
        return default


def recommended_candidates(vacancy_id, limit=5):
    """Топ кандидатів для вакансії: [{'candidate_id', 'score', 'matched', 'missing', ...}]."""
    data = _safe(lambda: get_client().candidates_for_vacancy(vacancy_id, limit=limit), None)
    return (data or {}).get('results', [])


def recommended_vacancies(candidate_id, limit=5):
    data = _safe(lambda: get_client().vacancies_for_candidate(candidate_id, limit=limit), None)
    return (data or {}).get('results', [])
