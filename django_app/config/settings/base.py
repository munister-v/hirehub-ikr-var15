"""Спільні налаштування. Усі секрети й параметри середовища читаються через django-environ."""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
# локально змінні можна покласти у django_app/.env або в корінь репозиторію (.env);
# у Docker вони приходять із середовища контейнера
for candidate in (BASE_DIR / '.env', BASE_DIR.parent / '.env'):
    if candidate.exists():
        environ.Env.read_env(candidate)

SECRET_KEY = env('DJANGO_SECRET_KEY', default='insecure-dev-key-change-me-0123456789abcdef')
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])
CSRF_TRUSTED_ORIGINS = env.list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # сторонні
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    # власні застосунки
    'jobs',
    'accounts',
    'integration',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # захист від CSRF для веб-форм
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# База даних: у Docker — PostgreSQL (DATABASE_URL=postgres://...), локально — SQLite
DATABASES = {
    'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
}
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
DATABASES['default']['CONN_MAX_AGE'] = env.int('DB_CONN_MAX_AGE', default=60)

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'uk'
TIME_ZONE = 'Europe/Kyiv'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'jobs:vacancy_list'
LOGOUT_REDIRECT_URL = 'jobs:vacancy_list'

# Обмеження завантаження файлів (резюме) — перевірка на рівні Django і у валідаторі моделі
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
RESUME_MAX_SIZE_MB = 5
RESUME_ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx']

# ---------------------------------------------------------------- кеш
# Redis, якщо задано REDIS_URL; інакше локальна пам'ять процесу (locmem)
REDIS_URL = env('REDIS_URL', default='')
if REDIS_URL:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}}
else:
    CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'hirehub'}}
VACANCY_CACHE_SECONDS = env.int('VACANCY_CACHE_SECONDS', default=60)

# ---------------------------------------------------------------- Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticatedOrReadOnly',),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'api.exceptions.unified_exception_handler',
    # обмеження частоти запитів (захист входу від перебору паролів)
    'DEFAULT_THROTTLE_CLASSES': ('rest_framework.throttling.AnonRateThrottle',),
    'DEFAULT_THROTTLE_RATES': {'anon': '300/min', 'login': '10/min'},
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'HireHub Django REST API',
    'DESCRIPTION': 'Платформа пошуку роботи та рекрутингу: вакансії, кандидати, заявки, співбесіди.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'ENUM_NAME_OVERRIDES': {
        'VacancyStatusEnum': 'jobs.models.Vacancy.Status',
        'ApplicationStatusEnum': 'jobs.models.Application.Status',
    },
}

# ---------------------------------------------------------------- Celery
CELERY_BROKER_URL = env('CELERY_BROKER_URL', default=REDIS_URL or 'memory://localhost/')
CELERY_RESULT_BACKEND = env('CELERY_RESULT_BACKEND', default='cache+memory://')
# без брокера (локальна розробка, тести) завдання виконуються одразу, в процесі
CELERY_TASK_ALWAYS_EAGER = env.bool('CELERY_TASK_ALWAYS_EAGER', default=not REDIS_URL)
CELERY_TASK_EAGER_PROPAGATES = False
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    'close-expired-vacancies-daily': {
        'task': 'jobs.tasks.close_expired_vacancies',
        'schedule': 60 * 60 * 24,
    },
    'reindex-matching-hourly': {
        'task': 'integration.tasks.reindex_all',
        'schedule': 60 * 60,
    },
}

# ---------------------------------------------------------------- інтеграція з FastAPI
MATCHING_ENABLED = env.bool('MATCHING_ENABLED', default=True)
MATCHING_SERVICE_URL = env('MATCHING_SERVICE_URL', default='http://127.0.0.1:8006')
MATCHING_TIMEOUT_SECONDS = env.float('MATCHING_TIMEOUT_SECONDS', default=3.0)
# спільний секрет: Django підписує сервісний JWT, FastAPI перевіряє підпис
SHARED_JWT_SECRET = env('SHARED_JWT_SECRET', default='dev-shared-jwt-secret-change-me-32chars')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'simple': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'}},
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'}},
    'root': {'handlers': ['console'], 'level': env('DJANGO_LOG_LEVEL', default='INFO')},
}
