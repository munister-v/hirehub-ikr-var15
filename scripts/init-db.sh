#!/bin/sh
# Виконується один раз при першому старті контейнера PostgreSQL: окрема БД для кожного сервісу
# (прямий доступ однієї служби до БД іншої заборонений — у кожної свої база й сховище).
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
    CREATE DATABASE ${DJANGO_DB};
    CREATE DATABASE ${FASTAPI_DB};
SQL
