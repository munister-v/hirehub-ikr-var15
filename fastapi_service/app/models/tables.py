"""ORM-моделі (SQLAlchemy 2.0, типізовані Mapped). Це власна БД сервісу: прямого доступу до БД Django немає —
дані потрапляють лише через HTTP-індексацію (POST /index/...)."""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """Користувач сервісу з роллю: admin | service | viewer."""
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16), default='viewer')
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IndexedVacancy(Base):
    """Знімок вакансії з Django. Первинний ключ = id вакансії в Django (не автоінкремент)."""
    __tablename__ = 'indexed_vacancies'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    title: Mapped[str] = mapped_column(String(200))
    company: Mapped[str] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str] = mapped_column(String(120), default='')
    salary_min: Mapped[int | None] = mapped_column(nullable=True)
    salary_max: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skills: Mapped[list['VacancySkillIndex']] = relationship(
        back_populates='vacancy', cascade='all, delete-orphan', lazy='selectin')


class VacancySkillIndex(Base):
    __tablename__ = 'vacancy_skills'
    __table_args__ = (UniqueConstraint('vacancy_id', 'skill_key', name='uq_vacancy_skill'),
                      Index('ix_vacancy_skills_key', 'skill_key'))

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey('indexed_vacancies.id', ondelete='CASCADE'))
    skill_key: Mapped[str] = mapped_column(String(80))      # нормалізована назва (нижній регістр)
    skill_name: Mapped[str] = mapped_column(String(80))
    level: Mapped[int] = mapped_column(default=3)

    vacancy: Mapped[IndexedVacancy] = relationship(back_populates='skills')


class IndexedCandidate(Base):
    __tablename__ = 'indexed_candidates'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    full_name: Mapped[str] = mapped_column(String(200))
    headline: Mapped[str] = mapped_column(String(200), default='')
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expected_salary: Mapped[int | None] = mapped_column(nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skills: Mapped[list['CandidateSkillIndex']] = relationship(
        back_populates='candidate', cascade='all, delete-orphan', lazy='selectin')


class CandidateSkillIndex(Base):
    __tablename__ = 'candidate_skills'
    __table_args__ = (UniqueConstraint('candidate_id', 'skill_key', name='uq_candidate_skill'),
                      Index('ix_candidate_skills_key', 'skill_key'))

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey('indexed_candidates.id', ondelete='CASCADE'))
    skill_key: Mapped[str] = mapped_column(String(80))
    skill_name: Mapped[str] = mapped_column(String(80))
    level: Mapped[int] = mapped_column(default=3)

    candidate: Mapped[IndexedCandidate] = relationship(back_populates='skills')


class ApplicationEvent(Base):
    """Журнал змін статусу заявок (події від Django); джерело для WebSocket-сповіщень."""
    __tablename__ = 'application_events'

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(index=True)
    candidate_id: Mapped[int] = mapped_column(index=True)
    vacancy_id: Mapped[int]
    vacancy_title: Mapped[str] = mapped_column(String(200), default='')
    status: Mapped[str] = mapped_column(String(16))
    status_label: Mapped[str] = mapped_column(String(64), default='')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IndexJob(Base):
    """Фонове завдання пакетної переіндексації (BackgroundTasks)."""
    __tablename__ = 'index_jobs'

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default='pending')   # pending | running | done | failed
    vacancies_count: Mapped[int] = mapped_column(default=0)
    candidates_count: Mapped[int] = mapped_column(default=0)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
