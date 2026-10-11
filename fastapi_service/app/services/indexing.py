"""Індексація: оновлення знімків вакансій/кандидатів та фонова пакетна переіндексація."""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.session import session_factory
from app.repositories.events import EventRepository, JobRepository
from app.repositories.index import CandidateIndexRepository, VacancyIndexRepository
from app.schemas.indexing import CandidateIn, IndexAck, ReindexIn, StatsOut, VacancyIn

logger = logging.getLogger(__name__)


class IndexService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vacancies = VacancyIndexRepository(session)
        self.candidates = CandidateIndexRepository(session)
        self.jobs = JobRepository(session)

    async def index_vacancy(self, data: VacancyIn) -> IndexAck:
        created = await self.vacancies.upsert(data)
        await self.session.commit()
        return IndexAck(id=data.id, skills=len(data.skills), created=created)

    async def index_candidate(self, data: CandidateIn) -> IndexAck:
        created = await self.candidates.upsert(data)
        await self.session.commit()
        return IndexAck(id=data.id, skills=len(data.skills), created=created)

    async def delete_vacancy(self, vacancy_id: int) -> None:
        if not await self.vacancies.delete(vacancy_id):
            raise NotFoundError('Вакансію не знайдено в індексі.')
        await self.session.commit()

    async def delete_candidate(self, candidate_id: int) -> None:
        if not await self.candidates.delete(candidate_id):
            raise NotFoundError('Кандидата не знайдено в індексі.')
        await self.session.commit()

    async def create_job(self, payload: ReindexIn) -> str:
        job_id = str(uuid.uuid4())
        await self.jobs.create(job_id, len(payload.vacancies), len(payload.candidates))
        await self.session.commit()
        return job_id

    async def get_job(self, job_id: str):
        job = await self.jobs.get(job_id)
        if job is None:
            raise NotFoundError('Завдання не знайдено.')
        return job

    async def stats(self) -> StatsOut:
        return StatsOut(
            vacancies=await self.vacancies.count(), candidates=await self.candidates.count(),
            vacancy_skills=await self.vacancies.count_skills(), candidate_skills=await self.candidates.count_skills(),
            events=await EventRepository(self.session).count())


async def run_reindex(job_id: str, payload: ReindexIn) -> None:
    """Виконується у фоні (BackgroundTasks) у власній сесії БД: запит уже отримав 202."""
    async with session_factory()() as session:
        jobs = JobRepository(session)
        job = await jobs.get(job_id)
        if job is None:
            return
        job.status = 'running'
        await session.commit()
        try:
            vacancies, candidates = VacancyIndexRepository(session), CandidateIndexRepository(session)
            for item in payload.vacancies:
                await vacancies.upsert(item)
            for item in payload.candidates:
                await candidates.upsert(item)
            await jobs.finish(job)
        except Exception as exc:  # noqa: BLE001 — помилку фіксуємо у статусі завдання
            logger.exception('Переіндексація %s не вдалася', job_id)
            await session.rollback()
            job = await jobs.get(job_id)
            await jobs.finish(job, error=str(exc))
        await session.commit()
