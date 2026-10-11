"""Інвалідація кешу вакансій при будь-якій зміні вакансії чи її навичок."""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from . import cache
from .models import Vacancy, VacancySkill


@receiver([post_save, post_delete], sender=Vacancy)
@receiver([post_save, post_delete], sender=VacancySkill)
def bump_cache_version(sender, **kwargs):
    cache.bump_version()
