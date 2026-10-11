"""Адміністративна панель: list_display, фільтри, пошук, inlines, оптимізовані запити."""
from django.contrib import admin

from . import models


class VacancySkillInline(admin.TabularInline):
    model = models.VacancySkill
    extra = 1
    autocomplete_fields = ['skill']


class CandidateSkillInline(admin.TabularInline):
    model = models.CandidateSkill
    extra = 1
    autocomplete_fields = ['skill']


class ResumeInline(admin.TabularInline):
    model = models.Resume
    extra = 0


class InterviewInline(admin.TabularInline):
    model = models.Interview
    extra = 0


@admin.register(models.City)
class CityAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(models.Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(models.Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ['name']


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'city', 'created']
    list_filter = ['city']
    search_fields = ['name', 'user__username']
    list_select_related = ['user', 'city']
    raw_id_fields = ['user']


@admin.register(models.Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'headline', 'city', 'expected_salary']
    list_filter = ['city']
    search_fields = ['full_name', 'headline', 'user__username']
    list_select_related = ['city']
    raw_id_fields = ['user']
    inlines = [CandidateSkillInline, ResumeInline]


@admin.register(models.Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['title', 'company', 'city', 'category', 'salary_min', 'salary_max', 'status', 'created']
    list_filter = ['status', 'work_format', 'category', 'city']
    search_fields = ['title', 'description', 'company__name']
    list_select_related = ['company', 'city', 'category']  # без N+1 у списку
    date_hierarchy = 'created'
    inlines = [VacancySkillInline]
    actions = ['close_selected']

    @admin.action(description='Закрити вибрані вакансії')
    def close_selected(self, request, queryset):
        for vacancy in queryset:
            vacancy.status = models.Vacancy.Status.CLOSED
            vacancy.save(update_fields=['status', 'updated'])


@admin.register(models.Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'vacancy', 'status', 'created']
    list_filter = ['status', 'created']
    search_fields = ['candidate__full_name', 'vacancy__title']
    list_select_related = ['candidate', 'vacancy', 'vacancy__company']
    inlines = [InterviewInline]
    raw_id_fields = ['candidate', 'vacancy', 'resume']


@admin.register(models.Interview)
class InterviewAdmin(admin.ModelAdmin):
    list_display = ['application', 'scheduled_at', 'location']
    list_filter = ['scheduled_at']
    list_select_related = ['application__candidate', 'application__vacancy']
