"""Вебінтерфейс: список/картка вакансій, кабінети кандидата й роботодавця, заявки, співбесіди."""
from accounts.roles import is_candidate, is_employer
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, TemplateView, UpdateView
from integration.client import candidate_ws_token
from integration.services import recommended_candidates, recommended_vacancies

from .forms import (
    ApplicationForm,
    ApplicationStatusForm,
    CandidateProfileForm,
    CandidateSkillFormSet,
    InterviewForm,
    ResumeForm,
    VacancyForm,
    VacancySkillFormSet,
)
from .models import Application, Candidate, Category, City, Interview, Resume, Vacancy
from .services import cached_vacancy_ids, clean_params, vacancies_by_ids

PAGE_SIZE = 10


# ---------------------------------------------------------------- допоміжні міксини
class EmployerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Лише роботодавці (мають профіль Company)."""
    raise_exception = False

    def test_func(self):
        return is_employer(self.request.user)


class CandidateRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_candidate(self.request.user)


# ---------------------------------------------------------------- публічна частина
class VacancyListView(TemplateView):
    """Каталог відкритих вакансій: фільтри (місто, категорія, зарплата, навички), пошук, пагінація, кеш id."""
    template_name = 'jobs/vacancy_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = clean_params(self.request.GET)
        ids = cached_vacancy_ids(params)
        page = Paginator(ids, PAGE_SIZE).get_page(self.request.GET.get('page'))
        ctx.update(
            vacancies=vacancies_by_ids(list(page.object_list)),
            page_obj=page,
            params=params,
            cities=City.objects.all(),
            categories=Category.objects.all(),
            work_formats=Vacancy.WorkFormat.choices,
            total=page.paginator.count,
        )
        return ctx


class VacancyDetailView(DetailView):
    template_name = 'jobs/vacancy_detail.html'
    context_object_name = 'vacancy'

    def get_queryset(self):
        return Vacancy.objects.with_related()

    def get_object(self, queryset=None):
        vacancy = super().get_object(queryset)
        user = self.request.user
        owner = is_employer(user) and vacancy.company.user_id == user.pk
        if vacancy.status == Vacancy.Status.DRAFT and not (owner or user.is_staff):
            raise Http404('Вакансію не знайдено')
        self.is_owner = owner
        return vacancy

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        vacancy, user = self.object, self.request.user
        ctx['is_owner'] = self.is_owner
        if is_candidate(user):
            candidate = user.candidate
            existing = Application.objects.filter(candidate=candidate, vacancy=vacancy).first()
            ctx['application'] = existing
            ctx['can_apply'] = existing is None and vacancy.accepts_applications()
            ctx['apply_form'] = ApplicationForm(candidate=candidate)
        if self.is_owner:
            ctx['applications_count'] = vacancy.applications.count()
            ctx['recommended'] = recommended_candidates(vacancy.pk)
        return ctx


# ---------------------------------------------------------------- роботодавець
class EmployerDashboardView(EmployerRequiredMixin, TemplateView):
    template_name = 'jobs/employer_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['vacancies'] = (Vacancy.objects.filter(company=self.request.user.company)
                            .select_related('city', 'category')
                            .annotate(apps=Count('applications')))
        return ctx


class VacancyFormMixin:
    """Спільна логіка створення/редагування: форма вакансії + формсет навичок в одній транзакції."""
    model = Vacancy
    form_class = VacancyForm
    template_name = 'jobs/vacancy_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if 'skills_formset' not in ctx:
            ctx['skills_formset'] = VacancySkillFormSet(
                self.request.POST or None, instance=getattr(self, 'object', None))
        return ctx

    def form_valid(self, form):
        formset = VacancySkillFormSet(self.request.POST, instance=form.instance)
        if not formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, skills_formset=formset))
        with transaction.atomic():
            form.instance.company = self.request.user.company
            self.object = form.save()
            formset.instance = self.object
            formset.save()
        messages.success(self.request, 'Вакансію збережено.')
        return redirect(self.object.get_absolute_url())


class VacancyCreateView(PermissionRequiredMixin, EmployerRequiredMixin, VacancyFormMixin, CreateView):
    permission_required = 'jobs.add_vacancy'


class VacancyUpdateView(PermissionRequiredMixin, EmployerRequiredMixin, VacancyFormMixin, UpdateView):
    permission_required = 'jobs.change_vacancy'

    def get_queryset(self):
        # роботодавець редагує лише власні вакансії; чужа — 404
        return Vacancy.objects.filter(company=self.request.user.company)


class VacancyDeleteView(PermissionRequiredMixin, EmployerRequiredMixin, DeleteView):
    permission_required = 'jobs.delete_vacancy'
    template_name = 'jobs/vacancy_confirm_delete.html'
    success_url = reverse_lazy('jobs:employer_dashboard')

    def get_queryset(self):
        return Vacancy.objects.filter(company=self.request.user.company)


class VacancyApplicationsView(EmployerRequiredMixin, TemplateView):
    template_name = 'jobs/vacancy_applications.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        vacancy = get_object_or_404(Vacancy, pk=self.kwargs['pk'], company=self.request.user.company)
        applications = (vacancy.applications.select_related('candidate', 'candidate__city', 'resume')
                        .prefetch_related('interviews', 'candidate__candidate_skills__skill'))
        ctx.update(
            vacancy=vacancy,
            rows=[(a, ApplicationStatusForm(application=a)) for a in applications],
            recommended=recommended_candidates(vacancy.pk),
        )
        return ctx


class ApplicationStatusView(EmployerRequiredMixin, View):
    """POST: зміна статусу заявки за графом переходів."""
    http_method_names = ['post']

    def post(self, request, pk):
        application = get_object_or_404(
            Application.objects.select_related('vacancy'), pk=pk, vacancy__company=request.user.company)
        form = ApplicationStatusForm(request.POST, application=application)
        if form.is_valid():
            try:
                application.change_status(form.cleaned_data['status'])
                messages.success(request, f'Статус змінено: {application.get_status_display()}.')
            except ValidationError as exc:
                messages.error(request, '; '.join(exc.messages))
        else:
            messages.error(request, 'Недопустимий перехід статусу.')
        return redirect('jobs:vacancy_applications', pk=application.vacancy_id)


class InterviewCreateView(EmployerRequiredMixin, CreateView):
    model = Interview
    form_class = InterviewForm
    template_name = 'jobs/interview_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.application = get_object_or_404(
            Application.objects.select_related('candidate', 'vacancy'),
            pk=kwargs['pk'], vacancy__company=getattr(request.user, 'company', None))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['application'] = self.application
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        app = self.application
        if app.status == Application.Status.SUBMITTED:
            app.change_status(Application.Status.REVIEWED)   # призначення співбесіди означає, що заявку переглянуто
        if app.status == Application.Status.REVIEWED:
            app.change_status(Application.Status.INTERVIEW)
        form.instance.application = app
        form.save()
        messages.success(self.request, 'Співбесіду призначено.')
        return redirect('jobs:vacancy_applications', pk=app.vacancy_id)


# ---------------------------------------------------------------- кандидат
class CandidateCabinetView(CandidateRequiredMixin, TemplateView):
    template_name = 'jobs/candidate_cabinet.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        candidate = Candidate.objects.select_related('city').prefetch_related(
            'candidate_skills__skill', 'resumes').get(pk=self.request.user.candidate.pk)
        ctx.update(
            candidate=candidate,
            applications=candidate.applications.select_related('vacancy', 'vacancy__company')
            .prefetch_related('interviews'),
            recommended=self._recommended(candidate),
        )
        return ctx

    @staticmethod
    def _recommended(candidate):
        items = recommended_vacancies(candidate.pk)
        by_id = Vacancy.objects.with_related().in_bulk([i['vacancy_id'] for i in items])
        return [{**i, 'vacancy': by_id[i['vacancy_id']]} for i in items if i['vacancy_id'] in by_id]


class CandidateProfileView(CandidateRequiredMixin, View):
    template_name = 'jobs/candidate_profile.html'

    def _render(self, request, form, formset):
        return render(request, self.template_name, {'form': form, 'skills_formset': formset})

    def get(self, request):
        candidate = request.user.candidate
        return self._render(request, CandidateProfileForm(instance=candidate),
                            CandidateSkillFormSet(instance=candidate))

    def post(self, request):
        candidate = request.user.candidate
        form = CandidateProfileForm(request.POST, instance=candidate)
        formset = CandidateSkillFormSet(request.POST, instance=candidate)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            messages.success(request, 'Профіль збережено.')
            return redirect('jobs:candidate_cabinet')
        return self._render(request, form, formset)


class ResumeCreateView(CandidateRequiredMixin, CreateView):
    model = Resume
    form_class = ResumeForm
    template_name = 'jobs/resume_form.html'
    success_url = reverse_lazy('jobs:candidate_cabinet')

    def form_valid(self, form):
        form.instance.candidate = self.request.user.candidate
        messages.success(self.request, 'Резюме завантажено.')
        return super().form_valid(form)


class ApplyView(CandidateRequiredMixin, View):
    """POST: подання заявки. Унікальність (candidate, vacancy) гарантує БД, зрозуміле повідомлення — форма."""
    http_method_names = ['post']

    def post(self, request, pk):
        vacancy = get_object_or_404(Vacancy.objects.select_related('company'), pk=pk)
        candidate = request.user.candidate
        form = ApplicationForm(request.POST, candidate=candidate)
        if not vacancy.accepts_applications():
            messages.error(request, 'Вакансія закрита й не приймає заявок.')
        elif Application.objects.filter(candidate=candidate, vacancy=vacancy).exists():
            messages.error(request, 'Ви вже подали заявку на цю вакансію.')
        elif form.is_valid():
            application = form.save(commit=False)
            application.candidate, application.vacancy = candidate, vacancy
            application.save()
            messages.success(request, 'Заявку подано.')
        else:
            messages.error(request, 'Перевірте форму заявки.')
        return redirect(vacancy.get_absolute_url())


class WsTokenView(CandidateRequiredMixin, View):
    """JSON з короткоживучим токеном і адресою WebSocket для сторінки кабінету."""

    def get(self, request):
        candidate_id = request.user.candidate.pk
        base = settings.MATCHING_PUBLIC_WS_URL.rstrip('/')
        return JsonResponse({
            'url': f'{base}/ws/applications/{candidate_id}',
            'token': candidate_ws_token(candidate_id),
            'candidate_id': candidate_id,
        })
