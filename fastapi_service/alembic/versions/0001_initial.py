"""Початкова схема: користувачі, індекс вакансій і кандидатів, події заявок, фонові завдання

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('hashed_password', sa.String(128), nullable=False),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    op.create_table(
        'indexed_vacancies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('company', sa.String(200), nullable=False),
        sa.Column('city', sa.String(120)),
        sa.Column('category', sa.String(120), nullable=False),
        sa.Column('salary_min', sa.Integer()),
        sa.Column('salary_max', sa.Integer()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'vacancy_skills',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('vacancy_id', sa.Integer(), sa.ForeignKey('indexed_vacancies.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('skill_key', sa.String(80), nullable=False),
        sa.Column('skill_name', sa.String(80), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.UniqueConstraint('vacancy_id', 'skill_key', name='uq_vacancy_skill'),
    )
    op.create_index('ix_vacancy_skills_key', 'vacancy_skills', ['skill_key'])

    op.create_table(
        'indexed_candidates',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('full_name', sa.String(200), nullable=False),
        sa.Column('headline', sa.String(200), nullable=False),
        sa.Column('city', sa.String(120)),
        sa.Column('expected_salary', sa.Integer()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'candidate_skills',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('candidate_id', sa.Integer(), sa.ForeignKey('indexed_candidates.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('skill_key', sa.String(80), nullable=False),
        sa.Column('skill_name', sa.String(80), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False),
        sa.UniqueConstraint('candidate_id', 'skill_key', name='uq_candidate_skill'),
    )
    op.create_index('ix_candidate_skills_key', 'candidate_skills', ['skill_key'])

    op.create_table(
        'application_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=False),
        sa.Column('vacancy_id', sa.Integer(), nullable=False),
        sa.Column('vacancy_title', sa.String(200), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('status_label', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_application_events_application_id', 'application_events', ['application_id'])
    op.create_index('ix_application_events_candidate_id', 'application_events', ['candidate_id'])

    op.create_table(
        'index_jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('vacancies_count', sa.Integer(), nullable=False),
        sa.Column('candidates_count', sa.Integer(), nullable=False),
        sa.Column('error', sa.String(500)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    for table in ('index_jobs', 'application_events', 'candidate_skills', 'indexed_candidates',
                  'vacancy_skills', 'indexed_vacancies', 'users'):
        op.drop_table(table)
