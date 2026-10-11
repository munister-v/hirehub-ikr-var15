# Підготовка до захисту (відповіді на орієнтовні запитання)

**1. Чому підбір винесено в окремий FastAPI-сервіс, а не реалізовано в Django?**
Підбір — окрема обчислювальна задача без UI та без бізнес-правил заявок: вона читає лише знімок навичок і рахує подібність.
Сервіс масштабується окремо (більше реплік uvicorn), має власну БД та контракт OpenAPI, а Django лишається «системою запису».
Витрати: міжсервісна автентифікація, дублювання даних і узгодженість «зрештою».

**2. Як автентифікуються виклики між сервісами? Що, якщо сервіс недоступний?**
Django підписує сервісний JWT (HS256, `role=service`, TTL 5 хв) спільним секретом `SHARED_JWT_SECRET`; FastAPI перевіряє підпис і роль.
Синхронізація запускається `transaction.on_commit` через Celery з повторами; `integration/services.py` ловить збої й повертає
порожній результат — сторінки працюють без рекомендацій. Є тест `test_service_outage_does_not_break_saving`.

**3. Де використано транзакції? Як усунено N+1?**
`transaction.atomic`: збереження вакансії разом із навичками (`VacancyFormMixin.form_valid`, `VacancySerializer.create/update`),
реєстрація користувача з профілем (`RegistrationForm.save`), призначення співбесіди зі зміною статусу заявки.
N+1: `Vacancy.objects.with_related()` (`select_related` + `prefetch_related`), `list_select_related` в адмінці;
тести `test_list_query_count_does_not_grow_with_data` і `test_query_count_for_vacancy_list_is_constant` порівнюють кількість
запитів для 2 і 8–10 вакансій.

**4. Чим відрізняються синхронні та асинхронні ендпоінти FastAPI? Де це має значення?**
`async def` виконується в event loop і не блокує його під час очікування I/O (БД через `asyncpg`, WebSocket).
У проєкті всі ендпоінти — `async`, доступ до БД — `AsyncSession`. Синхронний код (наприклад, bcrypt) блокує loop —
у вхідному шляху `/auth/token` це короткий CPU-крок; за високого навантаження його виносять у пул потоків.

**5. Як влаштовано JWT в DRF і FastAPI? Ризики та заходи захисту?**
DRF: SimpleJWT (`access` 30 хв, `refresh` 1 день), логін обмежено 10 запитами/хв (scope `login`) + `limit_req` у nginx.
FastAPI: `OAuth2PasswordBearer`, PyJWT, роль береться з БД (а не з токена) для токенів сервісу; токен кандидата для WebSocket
живе 10 хв і дає лише власний потік статусів. Ризики: витік секрету (зберігається лише в середовищі), крадіжка токена (короткий TTL),
підміна алгоритму (явний `algorithms=['HS256']`).

**6. Як працюють міграції Django та Alembic? Покажіть створення нової міграції.**
Django: `python manage.py makemigrations jobs` порівнює моделі зі станом міграцій і створює файл; `migrate` застосовує.
Alembic: `alembic revision -m "..."` (або `--autogenerate`), `alembic upgrade head`; в `alembic/versions/0001_initial.py` — початкова
схема, `alembic/env.py` працює з асинхронним engine. У Docker FastAPI виконує `alembic upgrade head` у `entrypoint.sh`.

**7. Що описано в Dockerfile і docker-compose.yml? Навіщо багатоетапна збірка й reverse proxy?**
Етап `builder` збирає wheels, фінальний образ не містить компіляторів і кешу, процес працює від користувача `app` (uid 10001).
Compose піднімає PostgreSQL (дві БД), Redis, Django (gunicorn), Celery worker/beat, FastAPI (uvicorn) і nginx з healthcheck і
`depends_on: condition: service_healthy`. nginx — єдина точка входу: маршрутизація `/` і `/matching/`, WebSocket-upgrade,
ліміт запитів, ліміт тіла запиту, відсутність прямого доступу до сервісів.

**8. Що покривають тести? Як ізольовано зовнішні виклики?**
Django (57): модель і бізнес-правила, фільтри/кеш, права за ролями (веб і API), формат помилок, N+1, інтеграція.
FastAPI (34): скоринг, автентифікація, індекс/підбір, WebSocket, Alembic. Зовнішні HTTP-виклики Django → FastAPI
підмінюються `respx`; залежності FastAPI — через `dependency_overrides`; БД у тестах — SQLite in-memory.
