"""Сигнали: зміни вакансій, профілів і заявок надсилаються до Matching Service після коміту транзакції."""
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from jobs.models import Application, Candidate, CandidateSkill, Vacancy, VacancySkill

from . import tasks


def _later(task, pk):
    """on_commit: завдання стартує лише коли дані справді збережені."""
    if settings.MATCHING_ENABLED:
        transaction.on_commit(lambda: task.delay(pk))


@receiver(post_save, sender=Vacancy)
@receiver(post_delete, sender=Vacancy)
def vacancy_changed(sender, instance, **kwargs):
    _later(tasks.sync_vacancy, instance.pk)


@receiver(post_save, sender=VacancySkill)
@receiver(post_delete, sender=VacancySkill)
def vacancy_skill_changed(sender, instance, **kwargs):
    _later(tasks.sync_vacancy, instance.vacancy_id)


@receiver(post_save, sender=Candidate)
@receiver(post_delete, sender=Candidate)
def candidate_changed(sender, instance, **kwargs):
    _later(tasks.sync_candidate, instance.pk)


@receiver(post_save, sender=CandidateSkill)
@receiver(post_delete, sender=CandidateSkill)
def candidate_skill_changed(sender, instance, **kwargs):
    _later(tasks.sync_candidate, instance.candidate_id)


@receiver(post_save, sender=Application)
def application_saved(sender, instance, created, **kwargs):
    # подія про статус заявки → FastAPI розсилає її по WebSocket кандидату
    _later(tasks.notify_application_status, instance.pk)
