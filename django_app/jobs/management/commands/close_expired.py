"""Закриває відкриті вакансії, у яких минув термін прийому заявок: python manage.py close_expired"""
from django.core.management.base import BaseCommand

from jobs.tasks import close_expired


class Command(BaseCommand):
    help = 'Закриває прострочені вакансії (ручний запуск того самого завдання, що й Celery beat)'

    def handle(self, *args, **options):
        count = close_expired()
        self.stdout.write(self.style.SUCCESS(f'Закрито вакансій: {count}'))
