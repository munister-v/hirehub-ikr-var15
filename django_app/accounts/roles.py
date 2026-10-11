"""Ролі через групи й дозволи Django: Candidate (кандидат), Employer (роботодавець), адміністратор = superuser."""
from django.contrib.auth.models import Group, Permission

CANDIDATE_GROUP = 'Candidate'
EMPLOYER_GROUP = 'Employer'

# codename дозволів застосунку jobs, які отримує кожна роль
ROLE_PERMISSIONS = {
    CANDIDATE_GROUP: [
        'add_application', 'view_application', 'add_resume', 'view_resume', 'change_resume', 'delete_resume',
        'view_vacancy', 'view_interview', 'change_candidate',
    ],
    EMPLOYER_GROUP: [
        'add_vacancy', 'change_vacancy', 'delete_vacancy', 'view_vacancy',
        'view_application', 'change_application', 'add_interview', 'change_interview', 'view_interview',
        'view_candidate', 'change_company',
    ],
}


def ensure_groups():
    """Створює групи й призначає їм дозволи (ідемпотентно; викликається після migrate)."""
    for name, codenames in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=name)
        perms = Permission.objects.filter(content_type__app_label='jobs', codename__in=codenames)
        group.permissions.set(perms)


def is_employer(user) -> bool:
    return user.is_authenticated and hasattr(user, 'company')


def is_candidate(user) -> bool:
    return user.is_authenticated and hasattr(user, 'candidate')
