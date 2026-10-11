"""Pydantic v2: схеми запитів індексації (вхідний контракт від Django)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SkillLevel(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    level: int = Field(default=3, ge=1, le=5)

    @field_validator('name')
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError('назва навички не може бути порожньою')
        return value


class VacancyIn(BaseModel):
    id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    company: str = Field(max_length=200)
    city: str | None = None
    category: str = ''
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    skills: list[SkillLevel] = []

    @model_validator(mode='after')
    def salary_range(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValueError('salary_min не може перевищувати salary_max')
        return self


class CandidateIn(BaseModel):
    id: int = Field(gt=0)
    full_name: str = Field(min_length=1, max_length=200)
    headline: str = ''
    city: str | None = None
    expected_salary: int | None = Field(default=None, ge=0)
    skills: list[SkillLevel] = []


class ReindexIn(BaseModel):
    vacancies: list[VacancyIn] = []
    candidates: list[CandidateIn] = []


class IndexAck(BaseModel):
    id: int
    skills: int
    created: bool


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    vacancies_count: int
    candidates_count: int
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class JobAccepted(BaseModel):
    job_id: str
    status: str = 'pending'


class StatsOut(BaseModel):
    vacancies: int
    candidates: int
    vacancy_skills: int
    candidate_skills: int
    events: int
