"""Реєстрація, вхід (OAuth2PasswordBearer), хешування, ролі."""
from tests.conftest import bearer


def test_register_login_me(client):
    created = client.post('/auth/register', json={'username': 'newuser', 'password': 'strong-pass-1'})
    assert created.status_code == 201
    assert created.json()['role'] == 'viewer'          # публічна реєстрація не дає підвищених ролей
    assert 'password' not in created.text

    token = client.post('/auth/token', data={'username': 'newuser', 'password': 'strong-pass-1'})
    assert token.status_code == 200
    body = token.json()
    assert body['token_type'] == 'bearer' and body['role'] == 'viewer'

    me = client.get('/auth/me', headers=bearer(body['access_token']))
    assert me.status_code == 200 and me.json()['username'] == 'newuser'


def test_duplicate_username_conflict(client):
    payload = {'username': 'dupuser', 'password': 'strong-pass-1'}
    assert client.post('/auth/register', json=payload).status_code == 201
    second = client.post('/auth/register', json=payload)
    assert second.status_code == 409
    assert second.json()['error']['code'] == 'conflict'


def test_wrong_password_is_401_with_unified_error(client):
    client.post('/auth/register', json={'username': 'someone', 'password': 'strong-pass-1'})
    response = client.post('/auth/token', data={'username': 'someone', 'password': 'wrong-password'})
    assert response.status_code == 401
    assert response.json()['error']['code'] == 'unauthorized'


def test_password_hashing_roundtrip():
    from app.core.security import hash_password, verify_password

    hashed = hash_password('s3cret-pass')
    assert hashed != 's3cret-pass' and hashed.startswith('$2')       # bcrypt
    assert verify_password('s3cret-pass', hashed) is True
    assert verify_password('other', hashed) is False


def test_admin_can_create_service_user_but_viewer_cannot(client, admin_headers, viewer_headers):
    payload = {'username': 'svc1', 'password': 'service-pass-1', 'role': 'service'}
    assert client.post('/auth/users', json=payload, headers=viewer_headers).status_code == 403
    created = client.post('/auth/users', json=payload, headers=admin_headers)
    assert created.status_code == 201 and created.json()['role'] == 'service'


def test_protected_endpoint_without_token_is_401(client):
    assert client.get('/match/explain?vacancy_id=1&candidate_id=1').status_code == 401


def test_register_validation_error_is_422_unified(client):
    response = client.post('/auth/register', json={'username': 'x', 'password': 'short'})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'validation_error'
