"""Модель даних і бізнес-правила (сутність → обмеження → статуси)."""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone
from jobs.models import Application, Interview, Resume, Vacancy
from jobs.tasks import close_expired
from jobs.validators import validate_resume_file

pytestmark = pytest.mark.django_db


def test_salary_range_validation_in_clean(vacancy):
    vacancy.salary_min, vacancy.salary_max = 100, 50
    with pytest.raises(ValidationError) as exc:
        vacancy.full_clean()
    assert 'salary_max' in exc.value.message_dict


def test_salary_range_enforced_by_database(vacancy):
    with pytest.raises(IntegrityError), transaction.atomic():
        Vacancy.objects.filter(pk=vacancy.pk).update(salary_min=999999, salary_max=1)


def test_one_application_per_vacancy_per_candidate(vacancy, candidate):
    Application.objects.create(candidate=candidate, vacancy=vacancy)
    with pytest.raises(IntegrityError), transaction.atomic():
        Application.objects.create(candidate=candidate, vacancy=vacancy)


def test_closed_vacancy_does_not_accept_applications(vacancy, candidate):
    vacancy.status = Vacancy.Status.CLOSED
    vacancy.save()
    with pytest.raises(ValidationError):
        Application(candidate=candidate, vacancy=vacancy).full_clean()
    assert vacancy.accepts_applications() is False


def test_expired_vacancy_does_not_accept_applications(vacancy):
    vacancy.closes_at = timezone.localdate() - timedelta(days=1)
    assert vacancy.accepts_applications() is False


def test_application_status_graph(vacancy, candidate):
    app = Application.objects.create(candidate=candidate, vacancy=vacancy)
    with pytest.raises(ValidationError):          # подана → пропозиція неможливо
        app.change_status(Application.Status.OFFER)
    app.change_status(Application.Status.REVIEWED)
    app.change_status(Application.Status.INTERVIEW)
    app.change_status(Application.Status.OFFER)
    with pytest.raises(ValidationError):          # з фінального статусу переходів немає
        app.change_status(Application.Status.REJECTED)


def test_interview_cannot_be_in_the_past(vacancy, candidate):
    app = Application.objects.create(candidate=candidate, vacancy=vacancy)
    interview = Interview(application=app, scheduled_at=timezone.now() - timedelta(hours=1), location='Zoom')
    with pytest.raises(ValidationError):
        interview.full_clean()


def test_resume_validator_accepts_pdf_and_rejects_fakes(settings):
    validate_resume_file(SimpleUploadedFile('cv.pdf', b'%PDF-1.4 content'))
    with pytest.raises(ValidationError):
        validate_resume_file(SimpleUploadedFile('cv.exe', b'MZ...'))          # недозволений тип
    with pytest.raises(ValidationError):
        validate_resume_file(SimpleUploadedFile('cv.pdf', b'not a real pdf'))  # розширення не відповідає вмісту
    big = SimpleUploadedFile('cv.pdf', b'%PDF' + b'0' * (settings.RESUME_MAX_SIZE_MB * 1024 * 1024))
    with pytest.raises(ValidationError):
        validate_resume_file(big)                                              # завеликий


def test_close_expired_task_closes_only_expired(vacancy, company, category):
    vacancy.closes_at = timezone.localdate() - timedelta(days=2)
    vacancy.save()
    fresh = Vacancy.objects.create(company=company, title='Fresh', description='x', category=category,
                                   status=Vacancy.Status.OPEN, closes_at=timezone.localdate() + timedelta(days=5))
    assert close_expired() == 1
    vacancy.refresh_from_db()
    fresh.refresh_from_db()
    assert vacancy.status == Vacancy.Status.CLOSED and fresh.status == Vacancy.Status.OPEN


def test_resume_str_and_relations(candidate):
    resume = Resume.objects.create(candidate=candidate, file=SimpleUploadedFile('cv.pdf', b'%PDF-1.4 x'))
    assert str(candidate) in str(resume)
    resume.file.delete(save=False)
