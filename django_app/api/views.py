"""REST API (DRF): ViewSet-и, дії (@action), права за ролями, фільтрація, пошук, пагінація."""
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.roles import is_candidate, is_employer
from integration.services import recommended_candidates, recommended_vacancies
from jobs.models import Application, Candidate, Category, City, Interview, Skill, Vacancy

from .filters import ApplicationFilter, VacancyFilter
from .permissions import IsCandidate, IsEmployer, IsVacancyOwnerOrReadOnly
from .serializers import (ApplicationSerializer, ApplicationStatusSerializer, CandidateSerializer,
                          CategorySerializer, CitySerializer, InterviewSerializer, SkillSerializer,
                          VacancySerializer)


class LoginTokenView(TokenObtainPairView):
    """Отримання JWT. Окремий ліміт 10 запитів/хв захищає від перебору паролів."""
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class ReadOnlyLookupViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = None


class CityViewSet(ReadOnlyLookupViewSet):
    queryset = City.objects.all()
    serializer_class = CitySerializer


class CategoryViewSet(ReadOnlyLookupViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class SkillViewSet(ReadOnlyLookupViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer


class VacancyViewSet(viewsets.ModelViewSet):
    """Вакансії. Гості й кандидати бачать лише відкриті; роботодавець — відкриті та власні."""
    serializer_class = VacancySerializer
    filterset_class = VacancyFilter
    search_fields = ['title', 'description', 'company__name']
    ordering_fields = ['created', 'salary_min', 'salary_max', 'title']
    permission_classes = [IsVacancyOwnerOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = Vacancy.objects.with_related()
        if user.is_authenticated and user.is_staff:
            return qs
        if is_employer(user):
            return qs.filter(Q(status=Vacancy.Status.OPEN) | Q(company=user.company))
        return qs.open()

    def get_permissions(self):
        if self.action == 'create':
            return [IsEmployer()]
        if self.action in ('update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsVacancyOwnerOrReadOnly()]
        if self.action == 'apply':
            return [IsCandidate()]
        if self.action == 'recommendations':
            return [IsEmployer()]
        return [AllowAny()]

    def perform_create(self, serializer):
        serializer.save(company=self.request.user.company)

    @extend_schema(request=None, responses=ApplicationSerializer)
    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """Користувацька дія: подати заявку на вакансію від імені поточного кандидата."""
        vacancy = self.get_object()
        serializer = ApplicationSerializer(
            data={'vacancy': vacancy.pk, 'cover_letter': request.data.get('cover_letter', ''),
                  'resume': request.data.get('resume')},
            context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(candidate=request.user.candidate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def recommendations(self, request, pk=None):
        """Топ кандидатів від Matching Service (лише власник вакансії)."""
        vacancy = self.get_object()
        if vacancy.company.user_id != request.user.pk and not request.user.is_staff:
            return Response({'error': {'code': 'permission_denied', 'message': 'Ви не власник вакансії.',
                                       'details': None}}, status=status.HTTP_403_FORBIDDEN)
        return Response({'results': recommended_candidates(vacancy.pk)})


class CandidateViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Кандидати: список бачать роботодавці й адміністратор; кандидат керує лише власним профілем (/me/)."""
    serializer_class = CandidateSerializer
    search_fields = ['full_name', 'headline']
    ordering_fields = ['full_name', 'expected_salary']
    filterset_fields = ['city']

    def get_queryset(self):
        return Candidate.objects.select_related('city', 'user').prefetch_related('candidate_skills__skill')

    def get_permissions(self):
        if self.action in ('me', 'my_recommendations'):
            return [IsCandidate()]
        return [IsAuthenticated()]

    def list(self, request, *args, **kwargs):
        if not (is_employer(request.user) or request.user.is_staff):
            return Response({'error': {'code': 'permission_denied', 'message': 'Список кандидатів доступний '
                                       'лише роботодавцям.', 'details': None}}, status=status.HTTP_403_FORBIDDEN)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        candidate = self.get_object()
        allowed = (request.user.is_staff or candidate.user_id == request.user.pk or is_employer(request.user))
        if not allowed:
            return Response({'error': {'code': 'permission_denied', 'message': 'Профіль недоступний.',
                                       'details': None}}, status=status.HTTP_403_FORBIDDEN)
        return Response(self.get_serializer(candidate).data)

    @action(detail=False, methods=['get', 'patch'])
    def me(self, request):
        candidate = self.get_queryset().get(pk=request.user.candidate.pk)
        if request.method == 'PATCH':
            serializer = self.get_serializer(candidate, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            candidate = self.get_queryset().get(pk=candidate.pk)
        return Response(self.get_serializer(candidate).data)

    @action(detail=False, methods=['get'], url_path='me/recommendations')
    def my_recommendations(self, request):
        """Рекомендовані вакансії від Matching Service для поточного кандидата."""
        return Response({'results': recommended_vacancies(request.user.candidate.pk)})


class ApplicationViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                         viewsets.GenericViewSet):
    """Заявки: кандидат — свої; роботодавець — заявки на свої вакансії; чужі об'єкти недоступні."""
    serializer_class = ApplicationSerializer
    filterset_class = ApplicationFilter
    ordering_fields = ['created', 'status']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Application.objects.select_related('candidate', 'vacancy', 'vacancy__company', 'resume')
        if user.is_staff:
            return qs
        if is_employer(user):
            return qs.filter(vacancy__company=user.company)
        if is_candidate(user):
            return qs.filter(candidate=user.candidate)
        return qs.none()

    def get_permissions(self):
        if self.action == 'create':
            return [IsCandidate()]
        if self.action == 'set_status':
            return [IsEmployer()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(candidate=self.request.user.candidate)

    @extend_schema(request=ApplicationStatusSerializer, responses=ApplicationSerializer)
    @action(detail=True, methods=['post'], url_path='status')
    def set_status(self, request, pk=None):
        """applications/{id}/status — зміна статусу за графом: подана → переглянута → співбесіда → пропозиція/відмова."""
        application = self.get_object()
        serializer = ApplicationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['status']
        if not application.can_change_to(new_status):
            return Response(
                {'error': {'code': 'invalid_transition', 'message': 'Недозволений перехід статусу.',
                           'details': {'from': application.status, 'to': new_status}}},
                status=status.HTTP_409_CONFLICT)
        with transaction.atomic():
            application.change_status(new_status)
        return Response(ApplicationSerializer(application, context={'request': request}).data)


class InterviewViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                       mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = InterviewSerializer
    ordering_fields = ['scheduled_at']
    filterset_fields = ['application']

    def get_queryset(self):
        user = self.request.user
        qs = Interview.objects.select_related('application', 'application__candidate', 'application__vacancy',
                                              'application__vacancy__company')
        if user.is_staff:
            return qs
        if is_employer(user):
            return qs.filter(application__vacancy__company=user.company)
        if is_candidate(user):
            return qs.filter(application__candidate=user.candidate)
        return qs.none()

    def get_permissions(self):
        if self.action in ('create', 'destroy'):
            return [IsEmployer()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        with transaction.atomic():
            interview = serializer.save()
            application = interview.application
            # призначення співбесіди переводить заявку у статус «Співбесіда» за дозволеним графом
            for step in (Application.Status.REVIEWED, Application.Status.INTERVIEW):
                if application.can_change_to(step):
                    application.change_status(step)
