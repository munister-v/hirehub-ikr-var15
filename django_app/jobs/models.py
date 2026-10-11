"""Доменна модель платформи пошуку роботи та рекрутингу (варіант 15).

Зв'язки:
  User 1:1 Company, User 1:1 Candidate;
  Company 1:N Vacancy;  Vacancy M:N Skill (через VacancySkill);
  Candidate M:N Skill (через CandidateSkill з рівнем володіння);
  Candidate 1:N Resume;  Candidate/Vacancy 1:N Application;  Application 1:N Interview.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.urls import reverse
from django.utils import timezone

from .validators import validate_resume_file

User = settings.AUTH_USER_MODEL


class City(models.Model):
    name = models.CharField('Місто', max_length=120, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'місто'
        verbose_name_plural = 'міста'

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField('Назва', max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'категорія'
        verbose_name_plural = 'категорії'

    def __str__(self):
        return self.name


class Skill(models.Model):
    name = models.CharField('Навичка', max_length=80, unique=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'навичка'
        verbose_name_plural = 'навички'

    def __str__(self):
        return self.name


class Company(models.Model):
    """Профіль роботодавця: User ↔ Company, 1:1."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company')
    name = models.CharField('Назва компанії', max_length=200)
    website = models.URLField('Сайт', blank=True)
    description = models.TextField('Про компанію', blank=True)
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name='companies')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'компанія'
        verbose_name_plural = 'компанії'

    def __str__(self):
        return self.name


class Candidate(models.Model):
    """Профіль кандидата: User ↔ Candidate, 1:1; навички з рівнем — через CandidateSkill."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='candidate')
    full_name = models.CharField('ПІБ', max_length=200)
    headline = models.CharField('Посада / коротко про себе', max_length=200, blank=True)
    phone = models.CharField('Телефон', max_length=32, blank=True)
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name='candidates')
    expected_salary = models.PositiveIntegerField('Очікувана зарплата', null=True, blank=True)
    skills = models.ManyToManyField(Skill, through='CandidateSkill', related_name='candidates')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['full_name']
        verbose_name = 'кандидат'
        verbose_name_plural = 'кандидати'

    def __str__(self):
        return self.full_name


class VacancyQuerySet(models.QuerySet):
    def open(self):
        """Лише відкриті вакансії (чернетки й закриті не показуються кандидатам)."""
        return self.filter(status=Vacancy.Status.OPEN)

    def with_related(self):
        """Один JOIN замість N+1: компанія, місто, категорія та навички одним проходом."""
        return self.select_related('company', 'city', 'category').prefetch_related('vacancy_skills__skill')

    def expired(self):
        today = timezone.localdate()
        return self.filter(status=Vacancy.Status.OPEN, closes_at__lt=today)


class Vacancy(models.Model):
    class WorkFormat(models.TextChoices):
        OFFICE = 'office', 'Офіс'
        REMOTE = 'remote', 'Віддалено'
        HYBRID = 'hybrid', 'Гібрид'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Чернетка'
        OPEN = 'open', 'Відкрита'
        CLOSED = 'closed', 'Закрита'

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='vacancies')
    title = models.CharField('Назва', max_length=200)
    description = models.TextField('Опис')
    city = models.ForeignKey(City, null=True, blank=True, on_delete=models.SET_NULL, related_name='vacancies')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='vacancies')
    salary_min = models.PositiveIntegerField('Зарплата від', null=True, blank=True)
    salary_max = models.PositiveIntegerField('Зарплата до', null=True, blank=True)
    work_format = models.CharField('Формат роботи', max_length=10, choices=WorkFormat.choices,
                                   default=WorkFormat.OFFICE)
    status = models.CharField('Статус', max_length=10, choices=Status.choices, default=Status.DRAFT)
    skills = models.ManyToManyField(Skill, through='VacancySkill', related_name='vacancies')
    closes_at = models.DateField('Приймаємо заявки до', null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = VacancyQuerySet.as_manager()

    class Meta:
        ordering = ['-created']
        verbose_name = 'вакансія'
        verbose_name_plural = 'вакансії'
        indexes = [
            models.Index(fields=['status', '-created']),
            models.Index(fields=['salary_min']),
        ]
        constraints = [
            # зарплатна вилка: мінімум не більший за максимум (і на рівні БД)
            models.CheckConstraint(
                condition=Q(salary_min__isnull=True) | Q(salary_max__isnull=True) | Q(salary_min__lte=F('salary_max')),
                name='vacancy_salary_range_valid',
            ),
        ]

    def __str__(self):
        return f'{self.title} — {self.company}'

    def clean(self):
        if self.salary_min is not None and self.salary_max is not None and self.salary_min > self.salary_max:
            raise ValidationError({'salary_max': 'Максимальна зарплата має бути не меншою за мінімальну.'})

    def get_absolute_url(self):
        return reverse('jobs:vacancy_detail', args=[self.pk])

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    def accepts_applications(self):
        """Закрита вакансія не приймає заявок; прострочена за датою — теж."""
        if not self.is_open:
            return False
        return self.closes_at is None or self.closes_at >= timezone.localdate()


LEVEL_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class VacancySkill(models.Model):
    """Навичка вакансії з вимаганим рівнем 1–5."""
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='vacancy_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='vacancy_skills')
    level = models.PositiveSmallIntegerField('Вимаганий рівень', default=3, validators=LEVEL_VALIDATORS)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['vacancy', 'skill'], name='unique_vacancy_skill')]
        verbose_name = 'навичка вакансії'
        verbose_name_plural = 'навички вакансії'

    def __str__(self):
        return f'{self.skill} ({self.level})'


class CandidateSkill(models.Model):
    """Навичка кандидата з рівнем володіння 1–5."""
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='candidate_skills')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='candidate_skills')
    level = models.PositiveSmallIntegerField('Рівень володіння', default=3, validators=LEVEL_VALIDATORS)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['candidate', 'skill'], name='unique_candidate_skill')]
        verbose_name = 'навичка кандидата'
        verbose_name_plural = 'навички кандидата'

    def __str__(self):
        return f'{self.skill} ({self.level})'


class Resume(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='resumes')
    file = models.FileField('Файл резюме', upload_to='resumes/%Y/%m/', validators=[validate_resume_file])
    description = models.TextField('Опис', blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'резюме'
        verbose_name_plural = 'резюме'

    def __str__(self):
        return f'Резюме {self.candidate} ({self.uploaded_at:%Y-%m-%d})'


class Application(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'submitted', 'Подана'
        REVIEWED = 'reviewed', 'Переглянута'
        INTERVIEW = 'interview', 'Співбесіда'
        OFFER = 'offer', 'Пропозиція'
        REJECTED = 'rejected', 'Відмова'

    # дозволені переходи: подана → переглянута → співбесіда → пропозиція / відмова
    TRANSITIONS = {
        Status.SUBMITTED: {Status.REVIEWED, Status.REJECTED},
        Status.REVIEWED: {Status.INTERVIEW, Status.REJECTED},
        Status.INTERVIEW: {Status.OFFER, Status.REJECTED},
        Status.OFFER: set(),
        Status.REJECTED: set(),
    }

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='applications')
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    resume = models.ForeignKey(Resume, null=True, blank=True, on_delete=models.SET_NULL, related_name='applications')
    cover_letter = models.TextField('Супровідний лист', blank=True)
    status = models.CharField('Статус', max_length=10, choices=Status.choices, default=Status.SUBMITTED)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'заявка'
        verbose_name_plural = 'заявки'
        constraints = [
            # кандидат може подати лише одну заявку на вакансію
            models.UniqueConstraint(fields=['candidate', 'vacancy'], name='unique_application_per_vacancy'),
        ]

    def __str__(self):
        return f'{self.candidate} → {self.vacancy} [{self.get_status_display()}]'

    def clean(self):
        if self._state.adding and self.vacancy_id and not self.vacancy.accepts_applications():
            raise ValidationError('Вакансія закрита й не приймає заявок.')

    def can_change_to(self, new_status):
        return new_status in self.TRANSITIONS[self.Status(self.status)]

    def change_status(self, new_status):
        """Змінює статус за дозволеним графом переходів; інакше — ValidationError."""
        if not self.can_change_to(new_status):
            raise ValidationError(
                f'Перехід «{self.get_status_display()}» → «{self.Status(new_status).label}» недозволений.')
        self.status = new_status
        self.save(update_fields=['status', 'updated'])


class Interview(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='interviews')
    scheduled_at = models.DateTimeField('Дата й час')
    location = models.CharField('Місце або посилання', max_length=255)
    notes = models.TextField('Нотатки', blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_at']
        verbose_name = 'співбесіда'
        verbose_name_plural = 'співбесіди'

    def __str__(self):
        return f'Співбесіда {self.application} {self.scheduled_at:%d.%m.%Y %H:%M}'

    def clean(self):
        if self._state.adding and self.scheduled_at and self.scheduled_at < timezone.now():
            raise ValidationError({'scheduled_at': 'Співбесіду не можна призначити в минулому.'})
