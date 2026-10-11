import django_filters
from django.db.models import Q

from jobs.models import Application, Vacancy


class VacancyFilter(django_filters.FilterSet):
    """Фільтри вакансій: місто, категорія, формат, зарплата, навички (усі зазначені)."""
    salary_from = django_filters.NumberFilter(method='filter_salary_from', label='Зарплата від (верхня межа вакансії ≥)')
    salary_to = django_filters.NumberFilter(field_name='salary_min', lookup_expr='lte', label='Зарплата до')
    skills = django_filters.CharFilter(method='filter_skills', label='Навички через кому')

    class Meta:
        model = Vacancy
        fields = ['city', 'category', 'work_format', 'status', 'company']

    def filter_salary_from(self, queryset, name, value):
        return queryset.filter(Q(salary_max__gte=value) | Q(salary_max__isnull=True))

    def filter_skills(self, queryset, name, value):
        for skill in [s.strip() for s in value.split(',') if s.strip()]:
            queryset = queryset.filter(skills__name__iexact=skill)
        return queryset.distinct()


class ApplicationFilter(django_filters.FilterSet):
    class Meta:
        model = Application
        fields = ['status', 'vacancy']
