# Журнал перевірки (11.10.2026)

Перевірка виконувалась на macOS: Python 3.14 (локально) і Python 3.12 (образи Docker), Docker Engine через Colima.

| Що перевірено | Як | Результат |
|---|---|---|
| Тести Django | `scripts/dev.sh test` | 57 passed, покриття 92 % |
| Тести FastAPI | `scripts/dev.sh test` | 34 passed, покриття 95 % |
| Лінтер | `ruff check .` | All checks passed |
| Міграції Django синхронні з моделями | `manage.py makemigrations --check --dry-run` | No changes detected |
| Повний комплекс | `docker compose up --build -d` | 7 сервісів, усі healthy (`docs/compose-ps.txt`) |
| Вхід через nginx | `curl` `/`, `/api/docs/`, `/matching/docs`, `/matching/health` | HTTP 200 |
| Початкова індексація | `GET /matching/index/stats` | 18 вакансій, 10 кандидатів, 66+37 навичок |
| Django → FastAPI → відповідь | `GET /api/vacancies/{id}/recommendations/` | кандидати з відсотком збігу |
| WebSocket через nginx | зміна статусу заявки в API → повідомлення в сокеті кандидата | отримано `application_status` |

## Помилки, знайдені під час запуску в Docker, і виправлення

1. `alembic` як скрипт не бачив пакет `app` → `prepend_sys_path = .` в `alembic.ini`.
2. `celery beat` не міг записати файл розкладу в `/app` (користувач `app`) → `--schedule /tmp/celerybeat-schedule`.
3. Celery-контейнери успадковували HTTP-healthcheck образу → власний healthcheck воркера, для beat вимкнено.
4. Початкова індексація залежала від воркера Celery → виконується синхронно в `entrypoint.sh` після готовності FastAPI.
5. `docker compose` не приймав назву проєкту з кирилиці → `name: hirehub` у `docker-compose.yml`.
