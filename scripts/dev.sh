#!/bin/bash
# dev.sh — локальний запуск обох сервісів БЕЗ Docker (SQLite, кеш у пам'яті, Celery в eager-режимі).
#
#   scripts/dev.sh start    підготувати середовище й запустити Django (:8005) та FastAPI (:8006) у фоні
#   scripts/dev.sh stop     зупинити
#   scripts/dev.sh status   стан і адреси
#   scripts/dev.sh test     тести обох сервісів із покриттям
#   scripts/dev.sh logs     хвіст логів
#
# Повноцінний запуск комплексу (PostgreSQL, Redis, nginx) — docker compose up --build (див. README).
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/env"
PY="$VENV/bin/python"
LOGS="$ROOT/logs"
DJANGO_PORT="${DJANGO_PORT:-8005}"
FASTAPI_PORT="${FASTAPI_PORT:-8006}"
SECRET="${SHARED_JWT_SECRET:-dev-shared-jwt-secret-change-me-32chars}"
mkdir -p "$LOGS"

ensure_env() {
  if [ ! -x "$PY" ]; then
    echo "створюю віртуальне оточення $VENV"
    "$(command -v python3.14 || command -v python3.13 || command -v python3.12 || command -v python3)" -m venv "$VENV" || exit 1
  fi
  if ! "$PY" -c 'import django, fastapi, rest_framework' >/dev/null 2>&1; then
    echo "встановлюю залежності"
    "$PY" -m pip install -q --upgrade pip
    "$PY" -m pip install -q -r "$ROOT/django_app/requirements-dev.txt" -r "$ROOT/fastapi_service/requirements-dev.txt" || exit 1
  fi
}

django_env() {
  export DJANGO_SETTINGS_MODULE=config.settings.dev SHARED_JWT_SECRET="$SECRET"
  export MATCHING_SERVICE_URL="http://127.0.0.1:$FASTAPI_PORT" MATCHING_PUBLIC_WS_URL="ws://127.0.0.1:$FASTAPI_PORT"
}

fastapi_env() {
  export SHARED_JWT_SECRET="$SECRET" MATCHING_AUTO_CREATE_TABLES=true
  export MATCHING_DATABASE_URL="sqlite+aiosqlite:///$ROOT/fastapi_service/matching.db"
  export MATCHING_ADMIN_USERNAME="${MATCHING_ADMIN_USERNAME:-admin}" MATCHING_ADMIN_PASSWORD="${MATCHING_ADMIN_PASSWORD:-admin12345}"
  export MATCHING_CORS_ORIGINS="[\"http://127.0.0.1:$DJANGO_PORT\",\"http://localhost:$DJANGO_PORT\"]"
}

port_pid() { lsof -ti "tcp:$1" -sTCP:LISTEN 2>/dev/null | head -1; }

wait_http() {  # url, секунд
  for _ in $(seq 1 "${2:-30}"); do
    curl -s -o /dev/null "$1" && return 0; sleep 1
  done
  return 1
}

start() {
  ensure_env
  if [ -n "$(port_pid "$FASTAPI_PORT")" ] || [ -n "$(port_pid "$DJANGO_PORT")" ]; then
    echo "порти $DJANGO_PORT/$FASTAPI_PORT уже зайняті — спершу: scripts/dev.sh stop"; status; return 0
  fi
  fastapi_env
  # (cd; nohup … &) — саме так, а не `cd && nohup … &`: інакше у фон піде весь ланцюжок разом із виводом
  ( cd "$ROOT/fastapi_service" || exit 1
    nohup "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port "$FASTAPI_PORT" \
      >"$LOGS/fastapi.log" 2>&1 </dev/null & )
  wait_http "http://127.0.0.1:$FASTAPI_PORT/health" 30 || { echo "FastAPI не піднявся, див. logs/fastapi.log"; return 1; }

  django_env
  ( cd "$ROOT/django_app" || exit 1
    "$PY" manage.py migrate --noinput >"$LOGS/django-setup.log" 2>&1 || { cat "$LOGS/django-setup.log"; exit 1; }
    "$PY" manage.py seed_demo >>"$LOGS/django-setup.log" 2>&1
    "$PY" manage.py reindex_matching >>"$LOGS/django-setup.log" 2>&1
    nohup "$PY" manage.py runserver "127.0.0.1:$DJANGO_PORT" --noreload >"$LOGS/django.log" 2>&1 </dev/null & )
  wait_http "http://127.0.0.1:$DJANGO_PORT/" 30 || { echo "Django не піднявся, див. logs/django.log"; return 1; }
  status
}

stop() {
  for port in "$DJANGO_PORT" "$FASTAPI_PORT"; do
    pid="$(port_pid "$port")"
    [ -n "$pid" ] && kill "$pid" 2>/dev/null && echo "зупинено :$port (PID $pid)"
  done
  return 0
}

status() {
  for pair in "Django:$DJANGO_PORT:/" "FastAPI:$FASTAPI_PORT:/health"; do
    IFS=: read -r name port path <<<"$pair"
    if [ -n "$(port_pid "$port")" ]; then
      echo "● $name — http://127.0.0.1:$port$path  (HTTP $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port$path"))"
    else
      echo "○ $name — не запущено (:$port)"
    fi
  done
  echo "  Django-сайт : http://127.0.0.1:$DJANGO_PORT/     адмінка: /admin/  (admin / admin12345)"
  echo "  REST API    : http://127.0.0.1:$DJANGO_PORT/api/docs/"
  echo "  Matching    : http://127.0.0.1:$FASTAPI_PORT/docs   ReDoc: /redoc"
}

run_tests() {
  ensure_env
  rc=0
  ( cd "$ROOT/django_app" && "$PY" -m pytest --cov --cov-report=term --cov-fail-under=70 ) || rc=1
  ( cd "$ROOT/fastapi_service" && "$PY" -m pytest --cov=app --cov-report=term --cov-fail-under=70 ) || rc=1
  return $rc
}

case "${1:-}" in
  start)  start ;;
  stop)   stop ;;
  restart) stop; sleep 1; start ;;
  status) status ;;
  test)   run_tests ;;
  logs)   tail -n 40 -f "$LOGS"/*.log ;;
  *) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
esac
