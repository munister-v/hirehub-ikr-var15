from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register('vacancies', views.VacancyViewSet, basename='vacancy')
router.register('candidates', views.CandidateViewSet, basename='candidate')
router.register('applications', views.ApplicationViewSet, basename='application')
router.register('interviews', views.InterviewViewSet, basename='interview')
router.register('cities', views.CityViewSet, basename='city')
router.register('categories', views.CategoryViewSet, basename='category')
router.register('skills', views.SkillViewSet, basename='skill')

urlpatterns = [
    path('auth/token/', views.LoginTokenView.as_view(), name='token_obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('', include(router.urls)),
]
