"""Вебінтерфейс: каталог, фільтри, ролі, подання заявки, зміна статусу, співбесіда, реєстрація."""
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from jobs.models import Application, Candidate, Company, Interview, Vacancy
from jobs.services import filter_vacancies

from .conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_catalog_lists_open_vacancies_only(client, vacancy, company, category):
    Vacancy.objects.create(company=company, title='Прихована чернетка', description='x', category=category)
    response = client.get(reverse('jobs:vacancy_list'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'Python developer' in content and 'Прихована чернетка' not in content


def test_catalog_filters_by_skills_and_salary(client, vacancy, company, category, skills):
    other = Vacancy.objects.create(company=company, title='Excel analyst', description='x', category=category,
                                   salary_min=10000, salary_max=15000, status=Vacancy.Status.OPEN)
    other.vacancy_skills.create(skill=skills['Excel'], level=2)
    names = {v.title for v in filter_vacancies({'skill': 'python,django'})}
    assert names == {'Python developer'}
    names = {v.title for v in filter_vacancies({'salary_from': '40000'})}
    assert names == {'Python developer'}          # верхня межа Excel analyst — 15000


def test_catalog_pagination(client, company, category):
    for i in range(23):
        Vacancy.objects.create(company=company, title=f'V{i}', description='x', category=category,
                               status=Vacancy.Status.OPEN)
    page2 = client.get(reverse('jobs:vacancy_list'), {'page': 2})
    assert page2.status_code == 200 and page2.context['page_obj'].number == 2
    assert len(page2.context['vacancies']) == 10


def test_list_query_count_does_not_grow_with_data(client, company, category, city, skills, django_assert_max_num_queries):
    """N+1: кількість SQL-запитів не залежить від кількості вакансій."""
    def add(n):
        for i in range(n):
            v = Vacancy.objects.create(company=company, title=f'V{i}', description='x', category=category,
                                       city=city, status=Vacancy.Status.OPEN)
            v.vacancy_skills.create(skill=skills['Python'], level=3)
    add(2)
    cache.clear()
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    with CaptureQueriesContext(connection) as small:
        client.get(reverse('jobs:vacancy_list'))
    add(8)
    cache.clear()
    with CaptureQueriesContext(connection) as large:
        client.get(reverse('jobs:vacancy_list'))
    assert len(large) == len(small)


def test_list_is_cached_and_invalidated_on_change(client, vacancy):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    url = reverse('jobs:vacancy_list')
    with CaptureQueriesContext(connection) as cold:
        client.get(url)
    with CaptureQueriesContext(connection) as warm:
        client.get(url)
    assert len(warm) < len(cold)                   # id вакансій узято з кешу: менше запитів до БД

    vacancy.title = 'Змінена назва'
    vacancy.save()                                 # сигнал піднімає версію кешу → старий список недійсний
    assert 'Змінена назва' in client.get(url).content.decode()


def test_draft_vacancy_hidden_from_public_but_visible_to_owner(client, vacancy, company):
    vacancy.status = Vacancy.Status.DRAFT
    vacancy.save()
    url = reverse('jobs:vacancy_detail', args=[vacancy.pk])
    assert client.get(url).status_code == 404
    client.login(username=company.user.username, password=PASSWORD)
    assert client.get(url).status_code == 200


def test_404_page_is_custom(client):
    response = client.get('/vacancies/99999/')
    assert response.status_code == 404 and 'сторінку не знайдено' in response.content.decode()


def test_employer_creates_vacancy_with_skills(client, company, category, skills, city):
    client.login(username=company.user.username, password=PASSWORD)
    data = {
        'title': 'Backend', 'description': 'FastAPI + Django', 'category': category.pk, 'city': city.pk,
        'salary_min': 20000, 'salary_max': 40000, 'work_format': 'remote', 'status': 'open',
        'vacancy_skills-TOTAL_FORMS': '1', 'vacancy_skills-INITIAL_FORMS': '0',
        'vacancy_skills-MIN_NUM_FORMS': '0', 'vacancy_skills-MAX_NUM_FORMS': '1000',
        'vacancy_skills-0-skill': skills['Python'].pk, 'vacancy_skills-0-level': '4',
    }
    response = client.post(reverse('jobs:vacancy_create'), data)
    assert response.status_code == 302
    vacancy = Vacancy.objects.get(title='Backend')
    assert vacancy.company == company and vacancy.vacancy_skills.count() == 1


def test_vacancy_form_rejects_inverted_salary(client, company, category):
    client.login(username=company.user.username, password=PASSWORD)
    data = {'title': 'X', 'description': 'y', 'category': category.pk, 'salary_min': 90, 'salary_max': 10,
            'work_format': 'office', 'status': 'open',
            'vacancy_skills-TOTAL_FORMS': '0', 'vacancy_skills-INITIAL_FORMS': '0',
            'vacancy_skills-MIN_NUM_FORMS': '0', 'vacancy_skills-MAX_NUM_FORMS': '1000'}
    response = client.post(reverse('jobs:vacancy_create'), data)
    assert response.status_code == 200 and not Vacancy.objects.filter(title='X').exists()


def test_candidate_cannot_open_vacancy_create(client, candidate):
    client.login(username=candidate.user.username, password=PASSWORD)
    response = client.get(reverse('jobs:vacancy_create'))
    assert response.status_code in (302, 403)


def test_employer_cannot_edit_foreign_vacancy(client, vacancy, other_company):
    client.login(username=other_company.user.username, password=PASSWORD)
    assert client.get(reverse('jobs:vacancy_update', args=[vacancy.pk])).status_code == 404


def test_candidate_applies_once(client, vacancy, candidate):
    client.login(username=candidate.user.username, password=PASSWORD)
    url = reverse('jobs:vacancy_apply', args=[vacancy.pk])
    client.post(url, {'cover_letter': 'Привіт'})
    client.post(url, {'cover_letter': 'Ще раз'})
    assert Application.objects.filter(candidate=candidate, vacancy=vacancy).count() == 1


def test_closed_vacancy_rejects_application(client, vacancy, candidate):
    vacancy.status = Vacancy.Status.CLOSED
    vacancy.save()
    client.login(username=candidate.user.username, password=PASSWORD)
    client.post(reverse('jobs:vacancy_apply', args=[vacancy.pk]), {})
    assert Application.objects.count() == 0


def test_employer_changes_status_and_schedules_interview(client, vacancy, candidate, company):
    app = Application.objects.create(candidate=candidate, vacancy=vacancy)
    client.login(username=company.user.username, password=PASSWORD)
    client.post(reverse('jobs:application_status', args=[app.pk]), {'status': 'reviewed'})
    app.refresh_from_db()
    assert app.status == Application.Status.REVIEWED
    when = (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%dT%H:%M')
    client.post(reverse('jobs:interview_create', args=[app.pk]), {'scheduled_at': when, 'location': 'Zoom'})
    app.refresh_from_db()
    assert app.status == Application.Status.INTERVIEW and Interview.objects.filter(application=app).exists()


def test_invalid_status_transition_is_rejected(client, vacancy, candidate, company):
    app = Application.objects.create(candidate=candidate, vacancy=vacancy)
    client.login(username=company.user.username, password=PASSWORD)
    client.post(reverse('jobs:application_status', args=[app.pk]), {'status': 'offer'})
    app.refresh_from_db()
    assert app.status == Application.Status.SUBMITTED


def test_registration_creates_profile_and_group(client, db):
    from accounts.roles import ensure_groups
    ensure_groups()
    data = {'username': 'newcomer', 'email': 'n@example.com', 'password1': 'Str0ng!pass-1', 'password2': 'Str0ng!pass-1',
            'role': 'employer', 'display_name': 'Нова Компанія'}
    response = client.post(reverse('accounts:register'), data)
    assert response.status_code == 302
    company = Company.objects.get(name='Нова Компанія')
    assert company.user.groups.filter(name='Employer').exists()
    cand = {**data, 'username': 'newbie', 'email': 'c@example.com', 'role': 'candidate', 'display_name': 'Іван'}
    client.logout()
    client.post(reverse('accounts:register'), cand)
    assert Candidate.objects.filter(full_name='Іван').exists()


def test_candidate_cabinet_and_ws_token(client, candidate_with_skills):
    client.login(username=candidate_with_skills.user.username, password=PASSWORD)
    assert client.get(reverse('jobs:candidate_cabinet')).status_code == 200
    token = client.get(reverse('jobs:ws_token')).json()
    assert token['candidate_id'] == candidate_with_skills.pk and token['url'].endswith(f'/{candidate_with_skills.pk}')
