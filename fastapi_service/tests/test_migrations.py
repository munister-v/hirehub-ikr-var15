"""Alembic: ревізія 0001 створює всю схему на чистій БД."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_alembic_upgrade_head_creates_tables(tmp_path):
    db = tmp_path / 'migrated.db'
    env = {**os.environ, 'MATCHING_DATABASE_URL': f'sqlite+aiosqlite:///{db}'}
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT, env=env,
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    conn = sqlite3.connect(db)
    try:
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    assert {'users', 'indexed_vacancies', 'vacancy_skills', 'indexed_candidates', 'candidate_skills',
            'application_events', 'index_jobs', 'alembic_version'} <= names
