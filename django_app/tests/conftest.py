"""Фікстури Django-тестів: ролі, профілі, довідники, вакансії."""
import pytest
from accounts.roles import CANDIDATE_GROUP, EMPLOYER_GROUP
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from jobs.models import Candidate, CandidateSkill, Category, City, Company, Skill, Vacancy, VacancySkill
from rest_framework.test import APIClient

User = get_user_model()
PASSWORD = 'pass12345!'


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache
    cache.clear()


@pytest.fixture
def city(db):
    return City.objects.create(name='Київ')


@pytest.fixture
def category(db):
    return Category.objects.create(name='Розробка ПЗ', slug='dev')


@pytest.fixture
def skills(db):
    return {n: Skill.objects.create(name=n) for n in ('Python', 'Django', 'Docker', 'Excel')}


def make_employer(username='boss', name='ТехноСфера'):
    user = User.objects.create_user(username, f'{username}@example.com', PASSWORD)
    user.groups.add(Group.objects.get(name=EMPLOYER_GROUP))
    return Company.objects.create(user=user, name=name)


def make_candidate(username='cand', name='Олена Коваль', city=None):
    user = User.objects.create_user(username, f'{username}@example.com', PASSWORD)
    user.groups.add(Group.objects.get(name=CANDIDATE_GROUP))
    return Candidate.objects.create(user=user, full_name=name, city=city)


@pytest.fixture
def company(db):
    return make_employer()


@pytest.fixture
def other_company(db):
    return make_employer('boss2', 'Інша Компанія')


@pytest.fixture
def candidate(db, city):
    return make_candidate(city=city)


@pytest.fixture
def other_candidate(db):
    return make_candidate('cand2', 'Максим Бойко')


@pytest.fixture
def vacancy(db, company, city, category, skills):
    v = Vacancy.objects.create(company=company, title='Python developer', description='Backend', city=city,
                               category=category, salary_min=30000, salary_max=50000, status=Vacancy.Status.OPEN)
    VacancySkill.objects.create(vacancy=v, skill=skills['Python'], level=4)
    VacancySkill.objects.create(vacancy=v, skill=skills['Django'], level=3)
    return v


@pytest.fixture
def candidate_with_skills(candidate, skills):
    CandidateSkill.objects.create(candidate=candidate, skill=skills['Python'], level=5)
    CandidateSkill.objects.create(candidate=candidate, skill=skills['Django'], level=4)
    return candidate


@pytest.fixture
def api():
    return APIClient()


def login_api(api, user):
    response = api.post('/api/auth/token/', {'username': user.username, 'password': PASSWORD}, format='json')
    assert response.status_code == 200, response.content
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {response.json()["access"]}')
    return api


@pytest.fixture
def employer_api(company):
    return login_api(APIClient(), company.user)


@pytest.fixture
def other_employer_api(other_company):
    return login_api(APIClient(), other_company.user)


@pytest.fixture
def candidate_api(candidate):
    return login_api(APIClient(), candidate.user)
