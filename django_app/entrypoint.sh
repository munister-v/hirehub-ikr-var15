#!/bin/sh
# Старт контейнера Django: чекаємо БД, застосовуємо міграції, збираємо статику, створюємо адміна й демо-дані.
# Для celery-контейнерів встановлено RUN_SETUP=false — вони пропускають цей етап.
set -e

if [ "${RUN_SETUP:-true}" = "true" ]; then
  echo "[entrypoint] очікування бази даних і міграції…"
  i=0
  until python manage.py migrate --noinput; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then echo "[entrypoint] БД недоступна"; exit 1; fi
    sleep 2
  done
  python manage.py collectstatic --noinput >/dev/null

  # суперкористувач із змінних середовища (пароль не зберігається в образі)
  python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
U = get_user_model()
name, pwd = os.environ.get('DJANGO_SUPERUSER_USERNAME'), os.environ.get('DJANGO_SUPERUSER_PASSWORD')
if name and pwd and not U.objects.filter(username=name).exists():
    U.objects.create_superuser(name, os.environ.get('DJANGO_SUPERUSER_EMAIL', ''), pwd)
    print('[entrypoint] створено суперкористувача', name)
"
  if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
    python manage.py seed_demo || true
  fi
  # початкова синхронізація індексу Matching Service (далі — сигнали та щогодинне завдання beat)
  python manage.py reindex_matching || true
fi

exec "$@"
