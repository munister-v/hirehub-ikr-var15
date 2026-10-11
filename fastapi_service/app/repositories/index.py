"""Репозиторії індексу вакансій і кандидатів (upsert, видалення, вибірки за спільними навичками)."""
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateSkillIndex, IndexedCandidate, IndexedVacancy, VacancySkillIndex


def skill_key(name: str) -> str:
    return name.strip().lower()


def _dedup(skills):
    """Одна навичка — один запис (за нормалізованим ім'ям); при дублі лишається вищий рівень."""
    best = {}
    for item in skills:
        key = skill_key(item.name)
        if key not in best or item.level > best[key].level:
            best[key] = item
    return best


class VacancyIndexRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, vacancy_id: int) -> IndexedVacancy | None:
        return await self.session.get(IndexedVacancy, vacancy_id)

    async def upsert(self, data) -> bool:
        """Створює або повністю оновлює вакансію разом з навичками. Повертає True, якщо створено."""
        vacancy = await self.get(data.id)
        created = vacancy is None
        if created:
            vacancy = IndexedVacancy(id=data.id, title=data.title, company=data.company)
            self.session.add(vacancy)
        vacancy.title, vacancy.company, vacancy.city = data.title, data.company, data.city
        vacancy.category, vacancy.salary_min, vacancy.salary_max = data.category, data.salary_min, data.salary_max
        if not created:
            await self.session.execute(delete(VacancySkillIndex).where(VacancySkillIndex.vacancy_id == data.id))
            await self.session.refresh(vacancy, ['skills'])
        vacancy.skills = [VacancySkillIndex(skill_key=k, skill_name=s.name, level=s.level)
                          for k, s in _dedup(data.skills).items()]
        await self.session.flush()
        return created

    async def delete(self, vacancy_id: int) -> bool:
        vacancy = await self.get(vacancy_id)
        if vacancy is None:
            return False
        await self.session.delete(vacancy)
        await self.session.flush()
        return True

    async def sharing_skills(self, keys: set[str]) -> list[IndexedVacancy]:
        """Вакансії, що мають хоча б одну з навичок keys (кандидати для порівняння)."""
        if not keys:
            return []
        ids = select(VacancySkillIndex.vacancy_id).where(VacancySkillIndex.skill_key.in_(keys))
        result = await self.session.execute(select(IndexedVacancy).where(IndexedVacancy.id.in_(ids)))
        return list(result.scalars().unique())

    async def count(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(IndexedVacancy))).scalar_one()

    async def count_skills(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(VacancySkillIndex))).scalar_one()


class CandidateIndexRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, candidate_id: int) -> IndexedCandidate | None:
        return await self.session.get(IndexedCandidate, candidate_id)

    async def upsert(self, data) -> bool:
        candidate = await self.get(data.id)
        created = candidate is None
        if created:
            candidate = IndexedCandidate(id=data.id, full_name=data.full_name)
            self.session.add(candidate)
        candidate.full_name, candidate.headline, candidate.city = data.full_name, data.headline, data.city
        candidate.expected_salary = data.expected_salary
        if not created:
            await self.session.execute(delete(CandidateSkillIndex).where(CandidateSkillIndex.candidate_id == data.id))
            await self.session.refresh(candidate, ['skills'])
        candidate.skills = [CandidateSkillIndex(skill_key=k, skill_name=s.name, level=s.level)
                            for k, s in _dedup(data.skills).items()]
        await self.session.flush()
        return created

    async def delete(self, candidate_id: int) -> bool:
        candidate = await self.get(candidate_id)
        if candidate is None:
            return False
        await self.session.delete(candidate)
        await self.session.flush()
        return True

    async def sharing_skills(self, keys: set[str]) -> list[IndexedCandidate]:
        if not keys:
            return []
        ids = select(CandidateSkillIndex.candidate_id).where(CandidateSkillIndex.skill_key.in_(keys))
        result = await self.session.execute(select(IndexedCandidate).where(IndexedCandidate.id.in_(ids)))
        return list(result.scalars().unique())

    async def count(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(IndexedCandidate))).scalar_one()

    async def count_skills(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(CandidateSkillIndex))).scalar_one()
