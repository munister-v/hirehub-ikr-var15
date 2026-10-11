"""REST API: JWT, права за ролями, фільтри, дії, формат помилок, OpenAPI."""
import pytest

from jobs.models import Application, Vacancy

pytestmark = pytest.mark.django_db


def test_token_obtain_and_invalid_credentials(api, candidate):
    ok = api.post('/api/auth/token/', {'username': candidate.user.username, 'password': 'pass12345!'}, format='json')
    assert ok.status_code == 200 and {'access', 'refresh'} <= set(ok.json())
    bad = api.post('/api/auth/token/', {'username': candidate.user.username, 'password': 'nope'}, format='json')
    assert bad.status_code == 401 and bad.json()['error']['code'] == 'authentication_failed'


def test_vacancies_are_public_and_paginated(api, vacancy):
    response = api.get('/api/vacancies/')
    assert response.status_code == 200
    body = response.json()
    assert body['count'] == 1 and body['results'][0]['title'] == 'Python developer'
    skills = {(s['skill'], s['level']) for s in body['results'][0]['skills']}
    assert skills == {('Python', 4), ('Django', 3)}


def test_anonymous_cannot_create_vacancy(api, category):
    response = api.post('/api/vacancies/', {'title': 'x', 'description': 'y', 'category': category.pk}, format='json')
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'not_authenticated'


def test_candidate_cannot_create_vacancy(candidate_api, category):
    response = candidate_api.post('/api/vacancies/', {'title': 'x', 'description': 'y', 'category': category.pk},
                                  format='json')
    assert response.status_code == 403 and response.json()['error']['code'] == 'permission_denied'


def test_employer_creates_vacancy_with_skills(employer_api, category, skills, company):
    payload = {'title': 'FastAPI dev', 'description': 'API', 'category': category.pk, 'salary_min': 1000,
               'salary_max': 2000, 'status': 'open', 'skills': [{'skill': 'Python', 'level': 5}]}
    response = employer_api.post('/api/vacancies/', payload, format='json')
    assert response.status_code == 201, response.content
    vacancy = Vacancy.objects.get(pk=response.json()['id'])
    assert vacancy.company == company and vacancy.vacancy_skills.get().level == 5


def test_inverted_salary_is_validation_error(employer_api, category):
    payload = {'title': 'X', 'description': 'y', 'category': category.pk, 'salary_min': 500, 'salary_max': 100}
    response = employer_api.post('/api/vacancies/', payload, format='json')
    assert response.status_code == 400
    error = response.json()['error']
    assert error['code'] == 'validation_error' and 'salary_max' in error['details']


def test_foreign_employer_cannot_modify_vacancy(other_employer_api, vacancy):
    response = other_employer_api.patch(f'/api/vacancies/{vacancy.pk}/', {'title': 'Hacked'}, format='json')
    assert response.status_code == 403
    vacancy.refresh_from_db()
    assert vacancy.title == 'Python developer'


def test_owner_can_update_and_delete(employer_api, vacancy):
    assert employer_api.patch(f'/api/vacancies/{vacancy.pk}/', {'title': 'Lead'}, format='json').status_code == 200
    assert employer_api.delete(f'/api/vacancies/{vacancy.pk}/').status_code == 204


def test_filters_search_and_ordering(api, vacancy, company, category, skills):
    other = Vacancy.objects.create(company=company, title='Excel analyst', description='tables', category=category,
                                   salary_min=10000, salary_max=15000, status=Vacancy.Status.OPEN)
    other.vacancy_skills.create(skill=skills['Excel'], level=2)
    assert api.get('/api/vacancies/?skills=Python').json()['count'] == 1
    assert api.get('/api/vacancies/?salary_from=40000').json()['count'] == 1
    assert api.get('/api/vacancies/?search=tables').json()['results'][0]['title'] == 'Excel analyst'
    ordered = api.get('/api/vacancies/?ordering=salary_min').json()['results']
    assert [v['title'] for v in ordered] == ['Excel analyst', 'Python developer']


def test_candidate_applies_via_action(candidate_api, vacancy, candidate):
    response = candidate_api.post(f'/api/vacancies/{vacancy.pk}/apply/', {'cover_letter': 'Привіт'}, format='json')
    assert response.status_code == 201, response.content
    assert Application.objects.filter(candidate=candidate, vacancy=vacancy).exists()
    again = candidate_api.post(f'/api/vacancies/{vacancy.pk}/apply/', {}, format='json')
    assert again.status_code == 400                        # унікальність заявки


def test_candidate_sees_only_own_applications(candidate_api, vacancy, candidate, other_candidate):
    Application.objects.create(candidate=candidate, vacancy=vacancy)
    other_vacancy = Vacancy.objects.create(company=vacancy.company, title='Other', description='x',
                                           category=vacancy.category, status=Vacancy.Status.OPEN)
    Application.objects.create(candidate=other_candidate, vacancy=other_vacancy)
    results = candidate_api.get('/api/applications/').json()['results']
    assert len(results) == 1 and results[0]['vacancy'] == vacancy.pk


def test_employer_sets_status_and_invalid_transition_conflicts(employer_api, vacancy, candidate):
    app = Application.objects.create(candidate=candidate, vacancy=vacancy)
    ok = employer_api.post(f'/api/applications/{app.pk}/status/', {'status': 'reviewed'}, format='json')
    assert ok.status_code == 200 and ok.json()['status'] == 'reviewed'
    bad = employer_api.post(f'/api/applications/{app.pk}/status/', {'status': 'submitted'}, format='json')
    assert bad.status_code == 409 and bad.json()['error']['code'] == 'invalid_transition'


def test_candidate_cannot_change_status(candidate_api, vacancy, candidate):
    app = Application.objects.create(candidate=candidate, vacancy=vacancy)
    response = candidate_api.post(f'/api/applications/{app.pk}/status/', {'status': 'reviewed'}, format='json')
    assert response.status_code == 403


def test_candidate_list_hidden_from_candidates_and_phone_private(candidate_api, employer_api, candidate):
    assert candidate_api.get('/api/candidates/').status_code == 403
    listing = employer_api.get('/api/candidates/').json()['results']
    assert listing and 'phone' not in listing[0]
    me = candidate_api.get('/api/candidates/me/').json()
    assert 'phone' in me and me['full_name'] == candidate.full_name


def test_candidate_updates_profile_and_skills(candidate_api, skills):
    response = candidate_api.patch('/api/candidates/me/', {'headline': 'Backend',
                                   'skills': [{'skill': 'Python', 'level': 5}]}, format='json')
    assert response.status_code == 200
    assert response.json()['skills'] == [{'skill': 'Python', 'level': 5}]


def test_interview_create_moves_application_forward(employer_api, vacancy, candidate):
    from datetime import timedelta

    from django.utils import timezone
    app = Application.objects.create(candidate=candidate, vacancy=vacancy)
    when = (timezone.now() + timedelta(days=3)).isoformat()
    response = employer_api.post('/api/interviews/', {'application': app.pk, 'scheduled_at': when,
                                                      'location': 'Meet'}, format='json')
    assert response.status_code == 201, response.content
    app.refresh_from_db()
    assert app.status == Application.Status.INTERVIEW


def test_openapi_schema_and_docs(api):
    schema = api.get('/api/schema/')
    assert schema.status_code == 200 and b'HireHub' in schema.content
    assert api.get('/api/docs/').status_code == 200


def test_query_count_for_vacancy_list_is_constant(api, company, category, city, skills, django_assert_num_queries):
    """Список вакансій з пов'язаними об'єктами: фіксована кількість запитів (без N+1)."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def make(n):
        for i in range(n):
            v = Vacancy.objects.create(company=company, title=f'T{i}', description='d', category=category,
                                       city=city, status=Vacancy.Status.OPEN)
            v.vacancy_skills.create(skill=skills['Python'], level=2)
            v.vacancy_skills.create(skill=skills['Django'], level=2)
    make(2)
    with CaptureQueriesContext(connection) as few:
        api.get('/api/vacancies/')
    make(6)
    with CaptureQueriesContext(connection) as many:
        api.get('/api/vacancies/')
    assert len(many) == len(few)
