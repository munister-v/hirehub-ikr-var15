"""WebSocket: статус заявки доставляється кандидату; перевірка токенів."""
import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.security import ISSUER_DJANGO, create_access_token

EVENT = {'application_id': 5, 'candidate_id': 10, 'vacancy_id': 1, 'status': 'interview',
         'status_label': 'Співбесіда', 'vacancy_title': 'Python developer'}


def candidate_token(candidate_id: int) -> str:
    return create_access_token(f'candidate:{candidate_id}', 'candidate', minutes=5, issuer=ISSUER_DJANGO,
                               extra={'candidate_id': candidate_id})


def test_status_event_is_pushed_to_connected_candidate(client, service_headers):
    with client.websocket_connect(f'/ws/applications/10?token={candidate_token(10)}') as ws:
        response = client.post('/applications/status', json=EVENT, headers=service_headers)
        assert response.status_code == 200 and response.json()['delivered_to'] == 1
        message = ws.receive_json()
        assert message['type'] == 'application_status'
        assert message['status'] == 'interview' and message['vacancy_title'] == 'Python developer'


def test_history_is_sent_on_connect(client, service_headers):
    client.post('/applications/status', json={**EVENT, 'status': 'submitted', 'status_label': 'Подана'},
                headers=service_headers)
    client.post('/applications/status', json=EVENT, headers=service_headers)
    with client.websocket_connect(f'/ws/applications/10?token={candidate_token(10)}') as ws:
        first = ws.receive_json()
        assert first['application_id'] == 5 and first['status'] == 'interview'    # лише останній статус заявки


def test_ping_pong(client):
    with client.websocket_connect(f'/ws/applications/10?token={candidate_token(10)}') as ws:
        ws.send_text('ping')
        assert ws.receive_json() == {'type': 'pong'}


def test_invalid_token_is_rejected(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect('/ws/applications/10?token=garbage'):
            pass
    assert exc.value.code == 4401


def test_other_candidates_token_is_forbidden(client):
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f'/ws/applications/10?token={candidate_token(99)}'):
            pass
    assert exc.value.code == 4403


def test_status_event_requires_service_role(client, viewer_headers):
    assert client.post('/applications/status', json=EVENT, headers=viewer_headers).status_code == 403
