"""Бізнес-логіка вибірок вакансій: фільтри, пошук, кешовані списки."""
from django.db.models import Q

from . import cache
from .models import Vacancy

FILTER_KEYS = ('q', 'city', 'category', 'salary_from', 'skill', 'work_format')


def clean_params(raw) -> dict:
    """Лишає лише відомі параметри фільтра (з QueryDict або dict)."""
    return {k: (raw.get(k) or '').strip() for k in FILTER_KEYS if (raw.get(k) or '').strip()}


def filter_vacancies(params: dict):
    """Відкриті вакансії за фільтрами: місто, категорія, зарплата, навички, формат, текстовий пошук."""
    qs = Vacancy.objects.open()
    if params.get('q'):
        qs = qs.filter(Q(title__icontains=params['q']) | Q(description__icontains=params['q'])
                       | Q(company__name__icontains=params['q']))
    if params.get('city'):
        qs = qs.filter(city_id=params['city'])
    if params.get('category'):
        qs = qs.filter(category_id=params['category'])
    if params.get('work_format'):
        qs = qs.filter(work_format=params['work_format'])
    if params.get('salary_from', '').isdigit():
        # вакансія підходить, якщо її верхня межа не нижча за очікуване (або межі не вказано)
        value = int(params['salary_from'])
        qs = qs.filter(Q(salary_max__gte=value) | Q(salary_max__isnull=True))
    if params.get('skill'):
        names = [n.strip() for n in params['skill'].split(',') if n.strip()]
        for name in names:  # усі вказані навички мають бути у вакансії
            qs = qs.filter(skills__name__iexact=name)
    return qs.distinct()


def cached_vacancy_ids(params: dict):
    return cache.get_or_compute_ids(params, lambda: filter_vacancies(params).values_list('pk', flat=True))


def vacancies_by_ids(ids):
    """Об'єкти у порядку ids; запити оптимізовані (select_related + prefetch_related)."""
    objs = Vacancy.objects.with_related().in_bulk(ids)
    return [objs[i] for i in ids if i in objs]
