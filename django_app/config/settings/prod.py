"""Налаштування для продакшну (docker compose): жодних значень за замовчуванням для секретів."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
SECRET_KEY = env('DJANGO_SECRET_KEY')            # без default: якщо не задано — помилка старту
SHARED_JWT_SECRET = env('SHARED_JWT_SECRET')

# ззовні трафік іде через nginx (reverse proxy) за HTTP на localhost; для HTTPS увімкніть:
SESSION_COOKIE_SECURE = env.bool('DJANGO_COOKIE_SECURE', default=False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
