from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(tags=['health'])


@router.get('/health')
async def health(session: AsyncSession = Depends(get_session)):
    """Перевірка живості та доступності БД — використовується healthcheck у docker-compose."""
    await session.execute(text('SELECT 1'))
    return {'status': 'ok', 'database': 'ok'}
