"""ModelForm-и вебінтерфейсу з власною валідацією."""
from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import (Application, Candidate, CandidateSkill, Interview, Resume, Vacancy, VacancySkill)


class VacancyForm(forms.ModelForm):
    class Meta:
        model = Vacancy
        fields = ['title', 'description', 'city', 'category', 'salary_min', 'salary_max',
                  'work_format', 'status', 'closes_at']
        widgets = {
            'closes_at': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 7}),
        }

    def clean_closes_at(self):
        value = self.cleaned_data.get('closes_at')
        if value and value < timezone.localdate():
            raise forms.ValidationError('Дата завершення прийому заявок не може бути в минулому.')
        return value


VacancySkillFormSet = inlineformset_factory(
    Vacancy, VacancySkill, fields=('skill', 'level'), extra=3, can_delete=True,
    widgets={'level': forms.NumberInput(attrs={'min': 1, 'max': 5})},
)


class CandidateProfileForm(forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ['full_name', 'headline', 'phone', 'city', 'expected_salary']


CandidateSkillFormSet = inlineformset_factory(
    Candidate, CandidateSkill, fields=('skill', 'level'), extra=3, can_delete=True,
    widgets={'level': forms.NumberInput(attrs={'min': 1, 'max': 5})},
)


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ['file', 'description']


class ApplicationForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ['resume', 'cover_letter']
        widgets = {'cover_letter': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, candidate=None, **kwargs):
        super().__init__(*args, **kwargs)
        # у списку лише власні резюме кандидата
        self.fields['resume'].queryset = Resume.objects.filter(candidate=candidate) if candidate else Resume.objects.none()
        self.fields['resume'].required = False
        self.fields['resume'].label = 'Резюме'


class ApplicationStatusForm(forms.Form):
    status = forms.ChoiceField(label='Новий статус')

    def __init__(self, *args, application, **kwargs):
        super().__init__(*args, **kwargs)
        self.application = application
        allowed = Application.TRANSITIONS[Application.Status(application.status)]
        self.fields['status'].choices = [(s.value, s.label) for s in Application.Status if s in allowed]


class InterviewForm(forms.ModelForm):
    class Meta:
        model = Interview
        fields = ['scheduled_at', 'location', 'notes']
        widgets = {
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
