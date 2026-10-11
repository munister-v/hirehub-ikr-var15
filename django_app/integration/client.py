"""HTTP-клієнт до FastAPI-сервісу «Matching Service».

Взаємодія — лише по HTTP (httpx) у форматі JSON. Кожен запит автентифікується сервісним JWT:
Django підписує токен спільним секретом SHARED_JWT_SECRET (HS256), FastAPI перевіряє підпис.
Недоступність сервісу не повинна ламати сайт: помилки перетворюються на MatchingUnavailable,
а виклики з веб-сторінок обгорнуті у безпечні функції (див. integration/services.py).
"""
import logging
import time

import httpx
import jwt
from django.conf import settings

logger = logging.getLogger(__name__)


class MatchingUnavailable(Exception):
    """Matching Service недоступний або повернув помилку."""


class MatchingClient:
    def __init__(self, base_url=None, secret=None, timeout=None, transport=None):
        self.base_url = (base_url or settings.MATCHING_SERVICE_URL).rstrip('/')
        self.secret = secret or settings.SHARED_JWT_SECRET
        self.timeout = timeout or settings.MATCHING_TIMEOUT_SECONDS
        self.transport = transport  # у тестах можна підставити httpx.MockTransport

    # ------------------------------------------------------------ автентифікація
    def service_token(self, ttl=300) -> str:
        now = int(time.time())
        payload = {'sub': 'django-service', 'role': 'service', 'iss': 'hirehub-django', 'iat': now, 'exp': now + ttl}
        return jwt.encode(payload, self.secret, algorithm='HS256')

    # ------------------------------------------------------------ транспорт
    def _request(self, method, path, **kwargs):
        headers = {'Authorization': f'Bearer {self.service_token()}'}
        try:
            with httpx.Client(base_url=self.base_url, timeout=self.timeout, transport=self.transport) as http:
                response = http.request(method, path, headers=headers, **kwargs)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning('Matching Service: %s %s — %s', method, path, exc)
            raise MatchingUnavailable(str(exc)) from exc
        return response.json() if response.content else None

    # ------------------------------------------------------------ індексація
    def index_vacancy(self, payload):
        return self._request('POST', '/index/vacancies', json=payload)

    def index_candidate(self, payload):
        return self._request('POST', '/index/candidates', json=payload)

    def delete_vacancy(self, vacancy_id):
        return self._request('DELETE', f'/index/vacancies/{vacancy_id}')

    def delete_candidate(self, candidate_id):
        return self._request('DELETE', f'/index/candidates/{candidate_id}')

    def reindex(self, vacancies, candidates):
        return self._request('POST', '/index/reindex', json={'vacancies': vacancies, 'candidates': candidates})

    # ------------------------------------------------------------ підбір
    def candidates_for_vacancy(self, vacancy_id, limit=5, metric='jaccard'):
        return self._request('GET', f'/match/vacancy/{vacancy_id}/candidates',
                             params={'limit': limit, 'metric': metric})

    def vacancies_for_candidate(self, candidate_id, limit=5, metric='jaccard'):
        return self._request('GET', f'/match/candidate/{candidate_id}/vacancies',
                             params={'limit': limit, 'metric': metric})

    def explain(self, vacancy_id, candidate_id):
        return self._request('GET', '/match/explain',
                             params={'vacancy_id': vacancy_id, 'candidate_id': candidate_id})

    # ------------------------------------------------------------ статуси заявок
    def notify_application_status(self, payload):
        return self._request('POST', '/applications/status', json=payload)


def get_client() -> MatchingClient:
    return MatchingClient()
