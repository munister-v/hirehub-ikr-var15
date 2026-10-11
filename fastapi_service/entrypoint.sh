#!/bin/sh
# Старт контейнера FastAPI: застосовуємо міграції Alembic (з повторами, поки БД не буде готова) і запускаємо сервер.
set -e
i=0
until alembic upgrade head; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then echo "[entrypoint] БД недоступна"; exit 1; fi
  sleep 2
done
exec "$@"
