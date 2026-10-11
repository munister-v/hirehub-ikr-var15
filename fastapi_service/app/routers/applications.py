"""Статуси заявок: прийом подій від Django і розсилка кандидатам по WebSocket."""
import logging

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import principal_from_token, require_roles
from app.db.session import get_session, session_factory
from app.repositories.events import EventRepository
from app.schemas.events import ApplicationEventOut, ApplicationStatusIn, StatusAck

logger = logging.getLogger(__name__)
router = APIRouter(tags=['applications'])


@router.post('/applications/status', response_model=StatusAck,
             dependencies=[Depends(require_roles('service', 'admin'))])
async def application_status(data: ApplicationStatusIn, request: Request, session: AsyncSession = Depends(get_session)):
    """Django повідомляє про зміну статусу заявки; подію зберігаємо й пересилаємо кандидату по WebSocket."""
    events = EventRepository(session)
    event = await events.add(**data.model_dump())
    await session.commit()
    payload = ApplicationEventOut.model_validate(event).model_dump(mode='json')
    delivered = await request.app.state.ws_manager.publish(data.candidate_id, {'type': 'application_status', **payload})
    return StatusAck(delivered_to=delivered)


@router.websocket('/ws/applications/{candidate_id}')
async def application_updates(websocket: WebSocket, candidate_id: int, token: str = ''):
    """WebSocket для кандидата. Токен — у query (?token=). Дозволено: service/admin або токен з candidate_id."""
    async with session_factory()() as session:
        try:
            principal = await principal_from_token(token, session)
        except AppError:
            await websocket.close(code=4401)
            return
        allowed = principal.role in ('service', 'admin') or principal.claims.get('candidate_id') == candidate_id
        if not allowed:
            await websocket.close(code=4403)
            return
        history = await EventRepository(session).latest_for_candidate(candidate_id)

    manager = websocket.app.state.ws_manager
    await websocket.accept()
    if not await manager.connect(candidate_id, websocket):
        await websocket.close(code=4429)
        return
    try:
        # одразу після підключення — поточні статуси заявок кандидата
        for event in history:
            payload = ApplicationEventOut.model_validate(event).model_dump(mode='json')
            await websocket.send_json({'type': 'application_status', **payload})
        while True:
            await websocket.receive_text()    # клієнт може надсилати ping; відповідаємо pong
            await websocket.send_json({'type': 'pong'})
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(candidate_id, websocket)
