"""Кешування списку вакансій у Redis (або locmem).

Кешується не HTML, а впорядкований перелік id відфільтрованих вакансій: це дешево для пам'яті,
а самі об'єкти для поточної сторінки підтягуються одним оптимізованим запитом.
Інвалідація — «версійним ключем»: будь-яка зміна вакансій збільшує версію, старі ключі застарівають.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache

VERSION_KEY = 'vacancies:version'


def current_version() -> int:
    return cache.get_or_set(VERSION_KEY, 1, timeout=None)


def bump_version() -> None:
    try:
        cache.incr(VERSION_KEY)
    except ValueError:        # ключа ще немає
        cache.set(VERSION_KEY, 2, timeout=None)


def list_key(params: dict) -> str:
    normalized = '&'.join(f'{k}={params[k]}' for k in sorted(params) if params[k] not in (None, ''))
    digest = hashlib.md5(normalized.encode(), usedforsecurity=False).hexdigest()
    return f'vacancies:list:v{current_version()}:{digest}'


def get_or_compute_ids(params: dict, compute):
    """compute() → ітерабельне з id. Результат кешується на VACANCY_CACHE_SECONDS."""
    key = list_key(params)
    ids = cache.get(key)
    if ids is None:
        ids = list(compute())
        cache.set(key, ids, settings.VACANCY_CACHE_SECONDS)
    return ids
