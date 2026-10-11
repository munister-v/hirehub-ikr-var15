"""Повна переіндексація Matching Service: python manage.py reindex_matching"""
from django.core.management.base import BaseCommand
from integration.tasks import reindex_all


class Command(BaseCommand):
    help = 'Надсилає у Matching Service усі відкриті вакансії та профілі кандидатів одним пакетом'

    def handle(self, *args, **options):
        result = reindex_all.apply().get()
        if result is None:
            self.stdout.write(self.style.WARNING('Сервіс недоступний або інтеграцію вимкнено (MATCHING_ENABLED).'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Переіндексацію прийнято: job_id={result.get("job_id")}'))
