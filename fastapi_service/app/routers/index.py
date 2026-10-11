from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.session import get_session
from app.schemas.indexing import CandidateIn, IndexAck, JobAccepted, JobOut, ReindexIn, StatsOut, VacancyIn
from app.services.indexing import IndexService, run_reindex

# записувати в індекс можуть лише сервіс (Django) та адміністратор
writer = Depends(require_roles('service', 'admin'))
router = APIRouter(prefix='/index', tags=['index'])


@router.post('/vacancies', response_model=IndexAck, dependencies=[writer])
async def index_vacancy(data: VacancyIn, session: AsyncSession = Depends(get_session)):
    """Оновлення індексу вакансії (Django надсилає після кожної зміни вакансії чи її навичок)."""
    return await IndexService(session).index_vacancy(data)


@router.post('/candidates', response_model=IndexAck, dependencies=[writer])
async def index_candidate(data: CandidateIn, session: AsyncSession = Depends(get_session)):
    return await IndexService(session).index_candidate(data)


@router.delete('/vacancies/{vacancy_id}', status_code=status.HTTP_204_NO_CONTENT, dependencies=[writer])
async def delete_vacancy(vacancy_id: int, session: AsyncSession = Depends(get_session)):
    await IndexService(session).delete_vacancy(vacancy_id)


@router.delete('/candidates/{candidate_id}', status_code=status.HTTP_204_NO_CONTENT, dependencies=[writer])
async def delete_candidate(candidate_id: int, session: AsyncSession = Depends(get_session)):
    await IndexService(session).delete_candidate(candidate_id)


@router.post('/reindex', response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED, dependencies=[writer])
async def reindex(payload: ReindexIn, background: BackgroundTasks, session: AsyncSession = Depends(get_session)):
    """Пакетна переіндексація: відповідь 202 одразу, робота виконується у фоні (BackgroundTasks)."""
    job_id = await IndexService(session).create_job(payload)
    background.add_task(run_reindex, job_id, payload)
    return JobAccepted(job_id=job_id)


@router.get('/jobs/{job_id}', response_model=JobOut, dependencies=[writer])
async def job_status(job_id: str, session: AsyncSession = Depends(get_session)):
    return await IndexService(session).get_job(job_id)


@router.get('/stats', response_model=StatsOut, dependencies=[writer])
async def stats(session: AsyncSession = Depends(get_session)):
    return await IndexService(session).stats()
