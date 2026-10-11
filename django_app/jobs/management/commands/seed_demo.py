"""Наповнення БД тестовими даними (>30 записів): python manage.py seed_demo [--force]

Створює міста, категорії, навички, роботодавців із вакансіями, кандидатів, заявки й співбесіди.
Команда ідемпотентна: якщо вакансії вже є, нічого не робить (без --force).
Облікові записи демо: admin / admin12345 (суперкористувач), employer1..5 і candidate1..10 / demo12345.
"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from accounts.roles import CANDIDATE_GROUP, EMPLOYER_GROUP, ensure_groups
from jobs.models import (Application, Candidate, CandidateSkill, Category, City, Company, Interview, Skill,
                         Vacancy, VacancySkill)

CITIES = ['Київ', 'Львів', 'Дніпро', 'Одеса', 'Харків', 'Ірпінь']
CATEGORIES = ['Розробка ПЗ', 'Дизайн', 'Маркетинг', 'Продажі', 'Підтримка клієнтів', 'Аналітика даних']
SKILLS = ['Python', 'Django', 'FastAPI', 'PostgreSQL', 'Docker', 'JavaScript', 'React', 'Git', 'Linux', 'SQL',
          'Figma', 'UX Research', 'SEO', 'Excel', 'Power BI', 'English B2', 'Комунікація', 'CRM', 'REST API', 'Redis']
COMPANIES = ['ТехноСфера', 'Дата Лаб', 'Креатив Хаб', 'Склад Плюс', 'Фінтех Ірпінь']
TITLES = {
    'Розробка ПЗ': ['Python-розробник', 'Backend-інженер Django', 'FastAPI-розробник', 'Fullstack-розробник',
                    'DevOps-інженер'],
    'Дизайн': ['UI/UX-дизайнер', 'Продуктовий дизайнер'],
    'Маркетинг': ['SEO-спеціаліст', 'Контент-маркетолог'],
    'Продажі': ['Менеджер із продажів', 'Sales-аналітик'],
    'Підтримка клієнтів': ['Спеціаліст підтримки', 'Team lead підтримки'],
    'Аналітика даних': ['Аналітик даних', 'BI-розробник'],
}
SKILL_SETS = {
    'Розробка ПЗ': ['Python', 'Django', 'FastAPI', 'PostgreSQL', 'Docker', 'Git', 'REST API', 'Redis', 'Linux'],
    'Дизайн': ['Figma', 'UX Research', 'English B2', 'Комунікація'],
    'Маркетинг': ['SEO', 'Excel', 'English B2', 'Комунікація'],
    'Продажі': ['CRM', 'Комунікація', 'Excel', 'English B2'],
    'Підтримка клієнтів': ['Комунікація', 'CRM', 'English B2', 'SQL'],
    'Аналітика даних': ['SQL', 'Python', 'Power BI', 'Excel', 'PostgreSQL'],
}
NAMES = ['Олена Коваль', 'Максим Бойко', 'Ірина Шевченко', 'Андрій Мельник', 'Софія Ткаченко', 'Тарас Лисенко',
         'Наталія Кравець', 'Богдан Олійник', 'Марія Гончар', 'Денис Поляк']


class Command(BaseCommand):
    help = 'Наповнює БД демонстраційними даними (міста, вакансії, кандидати, заявки)'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='додати дані, навіть якщо вакансії вже є')

    def handle(self, *args, **options):
        # під час масового створення синхронізацію з Matching Service вимикаємо,
        # а після — одним пакетом переіндексуємо (integration.tasks.reindex_all)
        with override_settings(MATCHING_ENABLED=False):
            created = self._seed(options)
        if created:
            from integration.tasks import reindex_all
            reindex_all.delay()

    @transaction.atomic
    def _seed(self, options):
        User = get_user_model()
        ensure_groups()
        if Vacancy.objects.exists() and not options['force']:
            self.stdout.write('Вакансії вже є — пропускаю (використайте --force).')
            return False
        rnd = random.Random(15)   # відтворювані дані

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin12345')

        cities = [City.objects.get_or_create(name=n)[0] for n in CITIES]
        categories = {n: Category.objects.get_or_create(name=n, defaults={'slug': f'cat-{i}'})[0]
                      for i, n in enumerate(CATEGORIES)}
        skills = {n: Skill.objects.get_or_create(name=n)[0] for n in SKILLS}

        employer_group = Group.objects.get(name=EMPLOYER_GROUP)
        candidate_group = Group.objects.get(name=CANDIDATE_GROUP)

        companies = []
        for i, name in enumerate(COMPANIES, start=1):
            user, created = User.objects.get_or_create(username=f'employer{i}', defaults={'email': f'hr{i}@example.com'})
            if created:
                user.set_password('demo12345')
                user.save()
                user.groups.add(employer_group)
            company, _ = Company.objects.get_or_create(
                user=user, defaults={'name': name, 'city': rnd.choice(cities), 'website': f'https://example.com/{i}'})
            companies.append(company)

        vacancies = []
        for company in companies:
            for _ in range(4):
                cat_name = rnd.choice(CATEGORIES)
                base = rnd.randint(2, 8) * 5000
                vacancy = Vacancy.objects.create(
                    company=company, title=rnd.choice(TITLES[cat_name]),
                    description=f'Запрошуємо до команди «{company.name}». Цікаві задачі, гнучкий графік, розвиток.',
                    city=rnd.choice(cities), category=categories[cat_name],
                    salary_min=base, salary_max=base + rnd.randint(1, 4) * 5000,
                    work_format=rnd.choice(Vacancy.WorkFormat.values),
                    status=Vacancy.Status.OPEN if rnd.random() > 0.1 else Vacancy.Status.CLOSED,
                    closes_at=timezone.localdate() + timedelta(days=rnd.randint(10, 60)),
                )
                pool = SKILL_SETS[cat_name]
                for name in rnd.sample(pool, k=min(len(pool), rnd.randint(3, 5))):
                    VacancySkill.objects.create(vacancy=vacancy, skill=skills[name], level=rnd.randint(2, 5))
                vacancies.append(vacancy)

        candidates = []
        for i, full_name in enumerate(NAMES, start=1):
            user, created = User.objects.get_or_create(
                username=f'candidate{i}', defaults={'email': f'candidate{i}@example.com'})
            if created:
                user.set_password('demo12345')
                user.save()
                user.groups.add(candidate_group)
            focus = rnd.choice(CATEGORIES)
            candidate, _ = Candidate.objects.get_or_create(user=user, defaults={
                'full_name': full_name, 'headline': rnd.choice(TITLES[focus]), 'city': rnd.choice(cities),
                'expected_salary': rnd.randint(2, 9) * 5000,
            })
            for name in rnd.sample(SKILL_SETS[focus], k=min(len(SKILL_SETS[focus]), rnd.randint(3, 5))):
                CandidateSkill.objects.get_or_create(
                    candidate=candidate, skill=skills[name], defaults={'level': rnd.randint(1, 5)})
            candidates.append(candidate)

        open_vacancies = [v for v in vacancies if v.is_open]
        flow = [Application.Status.SUBMITTED, Application.Status.REVIEWED, Application.Status.INTERVIEW,
                Application.Status.OFFER, Application.Status.REJECTED]
        applications = 0
        for candidate in candidates:
            for vacancy in rnd.sample(open_vacancies, k=2):
                application, created = Application.objects.get_or_create(
                    candidate=candidate, vacancy=vacancy,
                    defaults={'status': rnd.choice(flow), 'cover_letter': 'Цікавить ваша вакансія, готовий до співбесіди.'})
                if created:
                    applications += 1
                    if application.status in (Application.Status.INTERVIEW, Application.Status.OFFER):
                        Interview.objects.create(
                            application=application, scheduled_at=timezone.now() + timedelta(days=rnd.randint(1, 14)),
                            location='Google Meet', notes='Технічна співбесіда, 45 хв.')

        self.stdout.write(self.style.SUCCESS(
            f'Готово: міст {len(cities)}, категорій {len(categories)}, навичок {len(skills)}, компаній {len(companies)}, '
            f'вакансій {len(vacancies)}, кандидатів {len(candidates)}, заявок {applications}.'))
        return True
