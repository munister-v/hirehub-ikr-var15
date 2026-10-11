"""Індексація, підбір (Жаккар/косинус), пояснення, видалення, фонова переіндексація."""
import pytest

from tests.conftest import STRONG, VACANCY, WEAK, bearer


def test_health(client):
    response = client.get('/health')
    assert response.status_code == 200 and response.json() == {'status': 'ok', 'database': 'ok'}


def test_index_requires_service_or_admin_role(client, viewer_headers):
    response = client.post('/index/vacancies', json=VACANCY, headers=viewer_headers)
    assert response.status_code == 403
    assert response.json()['error']['code'] == 'forbidden'


def test_index_upsert_is_idempotent(client, service_headers):
    first = client.post('/index/vacancies', json=VACANCY, headers=service_headers).json()
    second = client.post('/index/vacancies', json={**VACANCY, 'title': 'Senior Python'}, headers=service_headers).json()
    assert first['created'] is True and second['created'] is False and second['skills'] == 3


def test_candidates_for_vacancy_jaccard(indexed, service_headers):
    response = indexed.get('/match/vacancy/1/candidates', headers=service_headers)
    assert response.status_code == 200
    data = response.json()
    assert data['metric'] == 'jaccard'
    names = [r['full_name'] for r in data['results']]
    assert names == ['Олена Коваль', 'Максим Бойко']              # сильніший кандидат першим
    top = data['results'][0]
    assert top['score'] == 1.0 and top['matched'] == ['Django', 'Docker', 'Python'] and top['missing'] == []
    assert data['results'][1]['missing'] == ['Django', 'Docker']


def test_cosine_metric_and_limit(indexed, service_headers):
    data = indexed.get('/match/vacancy/1/candidates?metric=cosine&limit=1', headers=service_headers).json()
    assert data['metric'] == 'cosine' and len(data['results']) == 1
    assert 0 < data['results'][0]['score'] <= 1


def test_min_score_filters_weak_candidates(indexed, service_headers):
    data = indexed.get('/match/vacancy/1/candidates?min_score=0.5', headers=service_headers).json()
    assert [r['candidate_id'] for r in data['results']] == [STRONG['id']]


def test_vacancies_for_candidate(indexed, service_headers):
    data = indexed.get(f'/match/candidate/{WEAK["id"]}/vacancies', headers=service_headers).json()
    assert data['results'][0]['vacancy_id'] == 1 and data['results'][0]['missing'] == ['Django', 'Docker']


def test_viewer_can_read_matches(indexed, viewer_headers):
    assert indexed.get('/match/vacancy/1/candidates', headers=viewer_headers).status_code == 200


def test_explain(indexed, service_headers):
    data = indexed.get(f'/match/explain?vacancy_id=1&candidate_id={WEAK["id"]}', headers=service_headers).json()
    assert [m['skill'] for m in data['missing']] == ['Django', 'Docker']
    assert [m['skill'] for m in data['extra']] == ['Excel']
    assert data['matched'][0]['skill'] == 'Python' and data['matched'][0]['sufficient'] is False   # 1 < 4


def test_unknown_vacancy_is_404(client, service_headers):
    response = client.get('/match/vacancy/999/candidates', headers=service_headers)
    assert response.status_code == 404 and response.json()['error']['code'] == 'not_found'


def test_delete_from_index(indexed, service_headers):
    assert indexed.delete('/index/candidates/10', headers=service_headers).status_code == 204
    assert indexed.delete('/index/candidates/10', headers=service_headers).status_code == 404
    data = indexed.get('/match/vacancy/1/candidates', headers=service_headers).json()
    assert [r['candidate_id'] for r in data['results']] == [WEAK['id']]


def test_validation_error_for_salary_range(client, service_headers):
    bad = {**VACANCY, 'salary_min': 90000, 'salary_max': 10000}
    response = client.post('/index/vacancies', json=bad, headers=service_headers)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'


def test_duplicate_skills_are_collapsed_to_highest_level(client, service_headers):
    payload = {**VACANCY, 'skills': [{'name': 'Python', 'level': 2}, {'name': 'PYTHON ', 'level': 5}]}
    assert client.post('/index/vacancies', json=payload, headers=service_headers).json()['skills'] == 2
    client.post('/index/candidates', json=STRONG, headers=service_headers)
    explain = client.get('/match/explain?vacancy_id=1&candidate_id=10', headers=service_headers).json()
    assert len(explain['matched']) == 1 and explain['matched'][0]['required'] == 5


def test_background_reindex_job(client, service_headers):
    payload = {'vacancies': [VACANCY], 'candidates': [STRONG, WEAK]}
    accepted = client.post('/index/reindex', json=payload, headers=service_headers)
    assert accepted.status_code == 202
    job = client.get(f'/index/jobs/{accepted.json()["job_id"]}', headers=service_headers).json()
    assert job['status'] == 'done' and job['vacancies_count'] == 1 and job['candidates_count'] == 2
    stats = client.get('/index/stats', headers=service_headers).json()
    assert stats['vacancies'] == 1 and stats['candidates'] == 2 and stats['candidate_skills'] == 5


def test_dependency_overrides_replace_authentication(client):
    """dependency_overrides: підміняємо автентифікацію й перевіряємо ендпоінт без реальних токенів."""
    from app.core.security import Principal, get_principal

    client.app.dependency_overrides[get_principal] = lambda: Principal(username='tester', role='admin')
    try:
        assert client.get('/index/stats', headers=bearer('anything')).status_code == 200
    finally:
        client.app.dependency_overrides.clear()


def test_openapi_and_docs_available(client):
    assert client.get('/openapi.json').status_code == 200
    assert client.get('/docs').status_code == 200
    assert client.get('/redoc').status_code == 200
