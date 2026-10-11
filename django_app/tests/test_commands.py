"""Команди керування: наповнення БД, закриття прострочених вакансій, переіндексація."""
from datetime import timedelta
from io import StringIO

import httpx
import pytest
import respx
from django.core.management import call_command
from django.utils import timezone
from jobs.models import Application, Candidate, Category, City, Skill, Vacancy

pytestmark = pytest.mark.django_db


def test_seed_demo_creates_enough_records_and_is_idempotent():
    call_command('seed_demo', stdout=StringIO())
    total = (City.objects.count() + Category.objects.count() + Skill.objects.count() + Vacancy.objects.count()
             + Candidate.objects.count() + Application.objects.count())
    assert total >= 30                      # вимога ІКР: не менше 30 записів
    before = Vacancy.objects.count()
    call_command('seed_demo', stdout=StringIO())
    assert Vacancy.objects.count() == before


def test_close_expired_command(vacancy):
    vacancy.closes_at = timezone.localdate() - timedelta(days=1)
    vacancy.save()
    out = StringIO()
    call_command('close_expired', stdout=out)
    vacancy.refresh_from_db()
    assert vacancy.status == Vacancy.Status.CLOSED and 'Закрито вакансій: 1' in out.getvalue()


@respx.mock
def test_reindex_matching_command(settings, vacancy):
    settings.MATCHING_ENABLED = True
    respx.post('http://matching.test/index/reindex').mock(return_value=httpx.Response(202, json={'job_id': 'j1'}))
    out = StringIO()
    call_command('reindex_matching', stdout=out)
    assert 'j1' in out.getvalue()
