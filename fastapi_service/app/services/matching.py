"""Підбір відповідностей: топ кандидатів для вакансії та рекомендовані вакансії для кандидата."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.repositories.index import CandidateIndexRepository, VacancyIndexRepository
from app.schemas.matching import (
    CandidateMatch,
    CandidatesResponse,
    ExplainResponse,
    Metric,
    SkillComparison,
    VacanciesResponse,
    VacancyMatch,
)
from app.services import scoring


def _skills(entity) -> scoring.Skills:
    return {s.skill_key: (s.skill_name, s.level) for s in entity.skills}


class MatchingService:
    def __init__(self, session: AsyncSession):
        self.vacancies = VacancyIndexRepository(session)
        self.candidates = CandidateIndexRepository(session)

    async def candidates_for_vacancy(self, vacancy_id: int, *, limit: int, metric: Metric,
                                     min_score: float) -> CandidatesResponse:
        vacancy = await self.vacancies.get(vacancy_id)
        if vacancy is None:
            raise NotFoundError('Вакансію не знайдено в індексі.')
        v_skills = _skills(vacancy)
        results = []
        for candidate in await self.candidates.sharing_skills(set(v_skills)):
            c_skills = _skills(candidate)
            value = scoring.score(metric.value, v_skills, c_skills)
            if value < min_score:
                continue
            matched, missing = scoring.matched_missing(v_skills, c_skills)
            results.append(CandidateMatch(
                candidate_id=candidate.id, full_name=candidate.full_name, headline=candidate.headline,
                city=candidate.city, score=value, score_percent=round(value * 100), matched=matched, missing=missing))
        results.sort(key=lambda r: (-r.score, r.candidate_id))
        return CandidatesResponse(vacancy_id=vacancy_id, metric=metric, results=results[:limit])

    async def vacancies_for_candidate(self, candidate_id: int, *, limit: int, metric: Metric,
                                      min_score: float) -> VacanciesResponse:
        candidate = await self.candidates.get(candidate_id)
        if candidate is None:
            raise NotFoundError('Кандидата не знайдено в індексі.')
        c_skills = _skills(candidate)
        results = []
        for vacancy in await self.vacancies.sharing_skills(set(c_skills)):
            v_skills = _skills(vacancy)
            value = scoring.score(metric.value, v_skills, c_skills)
            if value < min_score:
                continue
            matched, missing = scoring.matched_missing(v_skills, c_skills)
            results.append(VacancyMatch(
                vacancy_id=vacancy.id, title=vacancy.title, company=vacancy.company, city=vacancy.city,
                salary_min=vacancy.salary_min, salary_max=vacancy.salary_max, score=value,
                score_percent=round(value * 100), matched=matched, missing=missing))
        results.sort(key=lambda r: (-r.score, r.vacancy_id))
        return VacanciesResponse(candidate_id=candidate_id, metric=metric, results=results[:limit])

    async def explain(self, vacancy_id: int, candidate_id: int) -> ExplainResponse:
        vacancy = await self.vacancies.get(vacancy_id)
        candidate = await self.candidates.get(candidate_id)
        if vacancy is None or candidate is None:
            raise NotFoundError('Вакансію або кандидата не знайдено в індексі.')
        v_skills, c_skills = _skills(vacancy), _skills(candidate)
        matched, missing, extra = scoring.compare(v_skills, c_skills)
        return ExplainResponse(
            vacancy_id=vacancy_id, candidate_id=candidate_id,
            jaccard=scoring.score('jaccard', v_skills, c_skills), cosine=scoring.score('cosine', v_skills, c_skills),
            matched=[SkillComparison(**m) for m in matched], missing=[SkillComparison(**m) for m in missing],
            extra=[SkillComparison(**m) for m in extra])
