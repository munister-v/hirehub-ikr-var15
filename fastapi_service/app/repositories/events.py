from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApplicationEvent, IndexJob
from app.models.tables import utcnow


class EventRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, **fields) -> ApplicationEvent:
        event = ApplicationEvent(**fields)
        self.session.add(event)
        await self.session.flush()
        return event

    async def latest_for_candidate(self, candidate_id: int) -> list[ApplicationEvent]:
        """Останній статус кожної заявки кандидата."""
        latest = (select(ApplicationEvent.application_id, func.max(ApplicationEvent.id).label('max_id'))
                  .where(ApplicationEvent.candidate_id == candidate_id)
                  .group_by(ApplicationEvent.application_id).subquery())
        stmt = (select(ApplicationEvent).join(latest, ApplicationEvent.id == latest.c.max_id)
                .order_by(ApplicationEvent.id))
        return list((await self.session.execute(stmt)).scalars())

    async def count(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(ApplicationEvent))).scalar_one()


class JobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job_id: str, vacancies: int, candidates: int) -> IndexJob:
        job = IndexJob(id=job_id, status='pending', vacancies_count=vacancies, candidates_count=candidates)
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: str) -> IndexJob | None:
        return await self.session.get(IndexJob, job_id)

    async def finish(self, job: IndexJob, error: str | None = None) -> None:
        job.status = 'failed' if error else 'done'
        job.error = error[:500] if error else None
        job.finished_at = utcnow()
        await self.session.flush()
