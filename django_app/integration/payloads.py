"""Перетворення моделей Django на JSON-контракт FastAPI-сервісу (див. docs/openapi-fastapi.json)."""


def vacancy_payload(vacancy):
    return {
        'id': vacancy.pk,
        'title': vacancy.title,
        'company': vacancy.company.name,
        'city': vacancy.city.name if vacancy.city_id else None,
        'category': vacancy.category.name,
        'salary_min': vacancy.salary_min,
        'salary_max': vacancy.salary_max,
        'skills': [{'name': vs.skill.name, 'level': vs.level} for vs in vacancy.vacancy_skills.all()],
    }


def candidate_payload(candidate):
    return {
        'id': candidate.pk,
        'full_name': candidate.full_name,
        'headline': candidate.headline,
        'city': candidate.city.name if candidate.city_id else None,
        'expected_salary': candidate.expected_salary,
        'skills': [{'name': cs.skill.name, 'level': cs.level} for cs in candidate.candidate_skills.all()],
    }


def application_payload(application):
    return {
        'application_id': application.pk,
        'candidate_id': application.candidate_id,
        'vacancy_id': application.vacancy_id,
        'status': application.status,
        'status_label': application.get_status_display(),
        'vacancy_title': application.vacancy.title,
    }
