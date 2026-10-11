"""Взаємодія сервісів: Django → FastAPI (httpx), підміна зовнішніх викликів через respx."""
import json

import httpx
import jwt
import pytest
import respx
from django.test import override_settings
from integration.client import MatchingClient, MatchingUnavailable
from integration.services import recommended_candidates, recommended_vacancies
from jobs.models import Application, Vacancy

pytestmark = pytest.mark.django_db
BASE = 'http://matching.test'


@pytest.fixture
def enabled(settings):
    settings.MATCHING_ENABLED = True
    settings.CELERY_TASK_ALWAYS_EAGER = True
    return settings


def test_service_token_is_signed_with_shared_secret(settings):
    token = MatchingClient().service_token()
    claims = jwt.decode(token, settings.SHARED_JWT_SECRET, algorithms=['HS256'])
    assert claims['role'] == 'service' and claims['iss'] == 'hirehub-django'


@respx.mock
def test_saving_vacancy_sends_index_request_after_commit(enabled, company, category, skills, django_capture_on_commit_callbacks):
    route = respx.post(f'{BASE}/index/vacancies').mock(return_value=httpx.Response(200, json={'id': 1}))
    with django_capture_on_commit_callbacks(execute=True):
        vacancy = Vacancy.objects.create(company=company, title='Py', description='d', category=category,
                                         status=Vacancy.Status.OPEN)
        vacancy.vacancy_skills.create(skill=skills['Python'], level=4)
    assert route.called
    request = route.calls.last.request
    assert request.headers['Authorization'].startswith('Bearer ')
    payload = json.loads(request.content)
    assert payload['id'] == vacancy.pk and payload['skills'] == [{'name': 'Python', 'level': 4}]


@respx.mock
def test_closed_vacancy_is_removed_from_index(enabled, vacancy, django_capture_on_commit_callbacks):
    delete = respx.delete(f'{BASE}/index/vacancies/{vacancy.pk}').mock(return_value=httpx.Response(204))
    respx.post(f'{BASE}/index/vacancies').mock(return_value=httpx.Response(200, json={}))
    with django_capture_on_commit_callbacks(execute=True):
        vacancy.status = Vacancy.Status.CLOSED
        vacancy.save()
    assert delete.called


@respx.mock
def test_service_outage_does_not_break_saving(enabled, company, category, django_capture_on_commit_callbacks):
    respx.post(f'{BASE}/index/vacancies').mock(side_effect=httpx.ConnectError('down'))
    with django_capture_on_commit_callbacks(execute=True):
        vacancy = Vacancy.objects.create(company=company, title='Safe', description='d', category=category,
                                         status=Vacancy.Status.OPEN)
    assert Vacancy.objects.filter(pk=vacancy.pk).exists()          # збереження успішне попри недоступність сервісу


@respx.mock
def test_client_raises_on_error_status(enabled):
    respx.get(f'{BASE}/match/vacancy/1/candidates').mock(return_value=httpx.Response(500))
    with pytest.raises(MatchingUnavailable):
        MatchingClient().candidates_for_vacancy(1)


@respx.mock
def test_recommendations_parse_service_response(enabled):
    respx.get(f'{BASE}/match/vacancy/7/candidates').mock(return_value=httpx.Response(200, json={
        'results': [{'candidate_id': 3, 'full_name': 'Олена', 'score_percent': 80, 'matched': ['Python'],
                     'missing': []}]}))
    respx.get(f'{BASE}/match/candidate/3/vacancies').mock(side_effect=httpx.ConnectError('down'))
    assert recommended_candidates(7)[0]['full_name'] == 'Олена'
    assert recommended_vacancies(3) == []                          # збій → порожній результат, сторінка не падає


@respx.mock
def test_application_status_change_notifies_service(enabled, vacancy, candidate, django_capture_on_commit_callbacks):
    route = respx.post(f'{BASE}/applications/status').mock(return_value=httpx.Response(200, json={'stored': True}))
    respx.post(f'{BASE}/index/vacancies').mock(return_value=httpx.Response(200, json={}))
    respx.post(f'{BASE}/index/candidates').mock(return_value=httpx.Response(200, json={}))
    with django_capture_on_commit_callbacks(execute=True):
        app = Application.objects.create(candidate=candidate, vacancy=vacancy)
        app.change_status(Application.Status.REVIEWED)
    body = json.loads(route.calls.last.request.content)
    assert body['status'] == 'reviewed' and body['candidate_id'] == candidate.pk


@respx.mock
def test_reindex_all_sends_bulk_payload(enabled, vacancy, candidate_with_skills):
    route = respx.post(f'{BASE}/index/reindex').mock(return_value=httpx.Response(202, json={'job_id': 'abc'}))
    from integration.tasks import reindex_all
    assert reindex_all.apply().get() == {'job_id': 'abc'}
    body = json.loads(route.calls.last.request.content)
    assert len(body['vacancies']) == 1 and len(body['candidates']) == 1


@override_settings(MATCHING_ENABLED=False)
def test_integration_can_be_disabled(vacancy):
    assert recommended_candidates(vacancy.pk) == []
