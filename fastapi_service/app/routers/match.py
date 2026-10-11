from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_roles
from app.db.session import get_session
from app.schemas.matching import CandidatesResponse, ExplainResponse, Metric, VacanciesResponse
from app.services.matching import MatchingService

# читати підбір може будь-який автентифікований користувач (viewer, service, admin)
router = APIRouter(prefix='/match', tags=['match'], dependencies=[Depends(require_roles('admin', 'service', 'viewer'))])


@router.get('/vacancy/{vacancy_id}/candidates', response_model=CandidatesResponse)
async def candidates_for_vacancy(
    vacancy_id: int,
    limit: int = Query(10, ge=1, le=100),
    metric: Metric = Metric.jaccard,
    min_score: float = Query(0.0, ge=0, le=1),
    session: AsyncSession = Depends(get_session),
):
    """Топ кандидатів для вакансії за коефіцієнтом Жаккара або косинусною подібністю."""
    return await MatchingService(session).candidates_for_vacancy(
        vacancy_id, limit=limit, metric=metric, min_score=min_score)


@router.get('/candidate/{candidate_id}/vacancies', response_model=VacanciesResponse)
async def vacancies_for_candidate(
    candidate_id: int,
    limit: int = Query(10, ge=1, le=100),
    metric: Metric = Metric.jaccard,
    min_score: float = Query(0.0, ge=0, le=1),
    session: AsyncSession = Depends(get_session),
):
    """Рекомендовані вакансії для кандидата."""
    return await MatchingService(session).vacancies_for_candidate(
        candidate_id, limit=limit, metric=metric, min_score=min_score)


@router.get('/explain', response_model=ExplainResponse)
async def explain(vacancy_id: int, candidate_id: int, session: AsyncSession = Depends(get_session)):
    """Пояснення відповідності: які навички збіглися, яких бракує, що кандидат має додатково."""
    return await MatchingService(session).explain(vacancy_id, candidate_id)
