from django.urls import path

from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.VacancyListView.as_view(), name='vacancy_list'),
    path('vacancies/new/', views.VacancyCreateView.as_view(), name='vacancy_create'),
    path('vacancies/<int:pk>/', views.VacancyDetailView.as_view(), name='vacancy_detail'),
    path('vacancies/<int:pk>/edit/', views.VacancyUpdateView.as_view(), name='vacancy_update'),
    path('vacancies/<int:pk>/delete/', views.VacancyDeleteView.as_view(), name='vacancy_delete'),
    path('vacancies/<int:pk>/apply/', views.ApplyView.as_view(), name='vacancy_apply'),
    path('vacancies/<int:pk>/applications/', views.VacancyApplicationsView.as_view(), name='vacancy_applications'),
    path('applications/<int:pk>/status/', views.ApplicationStatusView.as_view(), name='application_status'),
    path('applications/<int:pk>/interview/', views.InterviewCreateView.as_view(), name='interview_create'),
    path('employer/', views.EmployerDashboardView.as_view(), name='employer_dashboard'),
    path('cabinet/', views.CandidateCabinetView.as_view(), name='candidate_cabinet'),
    path('cabinet/profile/', views.CandidateProfileView.as_view(), name='candidate_profile'),
    path('cabinet/resume/new/', views.ResumeCreateView.as_view(), name='resume_create'),
]
