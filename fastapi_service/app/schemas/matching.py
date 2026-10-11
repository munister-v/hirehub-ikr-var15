from enum import Enum

from pydantic import BaseModel, Field


class Metric(str, Enum):
    jaccard = 'jaccard'
    cosine = 'cosine'


class CandidateMatch(BaseModel):
    candidate_id: int
    full_name: str
    headline: str = ''
    city: str | None = None
    score: float = Field(ge=0, le=1)
    score_percent: int
    matched: list[str]
    missing: list[str]


class VacancyMatch(BaseModel):
    vacancy_id: int
    title: str
    company: str
    city: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    score: float = Field(ge=0, le=1)
    score_percent: int
    matched: list[str]
    missing: list[str]


class CandidatesResponse(BaseModel):
    vacancy_id: int
    metric: Metric
    results: list[CandidateMatch]


class VacanciesResponse(BaseModel):
    candidate_id: int
    metric: Metric
    results: list[VacancyMatch]


class SkillComparison(BaseModel):
    skill: str
    required: int | None = None
    actual: int | None = None
    sufficient: bool | None = None


class ExplainResponse(BaseModel):
    """Пояснення відповідності: які навички збіглися, яких бракує, що додатково."""
    vacancy_id: int
    candidate_id: int
    jaccard: float
    cosine: float
    matched: list[SkillComparison]
    missing: list[SkillComparison]
    extra: list[SkillComparison]
