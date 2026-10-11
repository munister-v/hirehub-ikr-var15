from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction

from jobs.models import Candidate, Company

from .roles import CANDIDATE_GROUP, EMPLOYER_GROUP

User = get_user_model()


class RegistrationForm(UserCreationForm):
    """Реєстрація з вибором ролі; одразу створюється профіль (Candidate або Company) і група."""
    ROLE_CHOICES = [('candidate', 'Кандидат — шукаю роботу'), ('employer', 'Роботодавець — шукаю працівників')]

    role = forms.ChoiceField(label='Хто ви?', choices=ROLE_CHOICES, widget=forms.RadioSelect, initial='candidate')
    display_name = forms.CharField(label='ПІБ або назва компанії', max_length=200)
    email = forms.EmailField(label='E-mail')

    class Meta:
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Користувач із таким e-mail уже зареєстрований.')
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=True)
        user.email = self.cleaned_data['email']
        user.save(update_fields=['email'])
        name = self.cleaned_data['display_name']
        if self.cleaned_data['role'] == 'employer':
            Company.objects.create(user=user, name=name)
            user.groups.add(Group.objects.get(name=EMPLOYER_GROUP))
        else:
            Candidate.objects.create(user=user, full_name=name)
            user.groups.add(Group.objects.get(name=CANDIDATE_GROUP))
        return user
