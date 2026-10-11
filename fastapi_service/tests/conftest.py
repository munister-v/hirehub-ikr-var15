"""Спільні фікстури FastAPI-тестів. Налаштування середовища задаються ДО імпорту застосунку."""
import os

os.environ['MATCHING_DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
os.environ['MATCHING_AUTO_CREATE_TABLES'] = 'true'
os.environ['MATCHING_BCRYPT_ROUNDS'] = '4'                       # швидкі хеші в тестах
os.environ['MATCHING_ADMIN_USERNAME'] = 'root'
os.environ['MATCHING_ADMIN_PASSWORD'] = 'root-password-1'
os.environ['SHARED_JWT_SECRET'] = 'test-shared-jwt-secret-with-32-plus-chars'

import pytest
from app.core.security import ISSUER_DJANGO, create_access_token
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient запускає lifespan: створює таблиці, адміністратора й менеджер WebSocket."""
    with TestClient(create_app()) as c:
        yield c


def bearer(token: str) -> dict:
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture
def service_headers():
    """Сервісний JWT, який у реальності видає Django (iss=hirehub-django)."""
    return bearer(create_access_token('django-service', 'service', minutes=5, issuer=ISSUER_DJANGO))


@pytest.fixture
def admin_headers(client):
    response = client.post('/auth/token', data={'username': 'root', 'password': 'root-password-1'})
    assert response.status_code == 200, response.text
    return bearer(response.json()['access_token'])


@pytest.fixture
def viewer_headers(client):
    client.post('/auth/register', json={'username': 'viewer1', 'password': 'viewer-pass-1'})
    token = client.post('/auth/token', data={'username': 'viewer1', 'password': 'viewer-pass-1'}).json()
    return bearer(token['access_token'])


VACANCY = {
    'id': 1, 'title': 'Python developer', 'company': 'TechCo', 'city': 'Київ', 'category': 'IT',
    'salary_min': 30000, 'salary_max': 50000,
    'skills': [{'name': 'Python', 'level': 4}, {'name': 'Django', 'level': 3}, {'name': 'Docker', 'level': 2}],
}
STRONG = {'id': 10, 'full_name': 'Олена Коваль', 'headline': 'Backend',
          'skills': [{'name': 'python', 'level': 5}, {'name': 'Django', 'level': 4}, {'name': 'Docker', 'level': 2}]}
WEAK = {'id': 11, 'full_name': 'Максим Бойко', 'headline': 'Junior',
        'skills': [{'name': 'Python', 'level': 1}, {'name': 'Excel', 'level': 5}]}


@pytest.fixture
def indexed(client, service_headers):
    """Індекс із однією вакансією та двома кандидатами."""
    assert client.post('/index/vacancies', json=VACANCY, headers=service_headers).status_code == 200
    for candidate in (STRONG, WEAK):
        assert client.post('/index/candidates', json=candidate, headers=service_headers).status_code == 200
    return client
