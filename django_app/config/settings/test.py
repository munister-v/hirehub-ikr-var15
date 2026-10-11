"""Налаштування для автоматичних тестів: ізольовано, швидко, без зовнішніх сервісів."""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = 'test-secret-key-with-more-than-32-characters'
SHARED_JWT_SECRET = 'test-shared-jwt-secret-with-32-plus-chars'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'tests'}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # швидко в тестах
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_TASK_ALWAYS_EAGER = True
MATCHING_ENABLED = False          # інтеграційні тести вмикають його явно (override_settings + respx)
MATCHING_SERVICE_URL = 'http://matching.test'
MEDIA_ROOT = BASE_DIR / 'media_test'
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}
REST_FRAMEWORK = {**REST_FRAMEWORK, 'DEFAULT_THROTTLE_CLASSES': ()}  # noqa: F405
MIDDLEWARE = [m for m in MIDDLEWARE if 'whitenoise' not in m]  # noqa: F405 — статика в тестах не потрібна
