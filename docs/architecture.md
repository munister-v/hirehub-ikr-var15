# Архітектура та взаємодія сервісів

```mermaid
flowchart LR
    Browser((Браузер)) -->|HTTP :8080| Nginx[nginx<br/>reverse proxy]
    Nginx -->|/ · /admin · /api| Django[Django + DRF<br/>gunicorn]
    Nginx -->|/matching/*<br/>HTTP + WebSocket| FastAPI[FastAPI<br/>uvicorn]
    Django --> PG1[(PostgreSQL<br/>hirehub_django)]
    FastAPI --> PG2[(PostgreSQL<br/>hirehub_matching)]
    Django --> Redis[(Redis<br/>кеш + брокер)]
    Celery[Celery worker/beat] --> Redis
    Celery --> PG1
    Django -. "httpx, сервісний JWT (JSON)" .-> FastAPI
    Celery -. "повторні спроби, reindex" .-> FastAPI
```

## Послідовність: зміна вакансії → індекс → рекомендації

```mermaid
sequenceDiagram
    actor E as Роботодавець
    participant D as Django
    participant C as Celery/eager
    participant F as FastAPI
    actor K as Кандидат
    E->>D: збереження вакансії (форма/API)
    D->>D: transaction.atomic → COMMIT
    D->>C: on_commit → sync_vacancy(id)
    C->>F: POST /index/vacancies (Bearer сервісний JWT)
    F-->>C: 200 {created}
    K->>D: кабінет кандидата
    D->>F: GET /match/candidate/{id}/vacancies
    F-->>D: топ вакансій (Жаккар) + matched/missing
    D-->>K: сторінка з рекомендаціями
```

## Послідовність: статус заявки → WebSocket

```mermaid
sequenceDiagram
    actor K as Кандидат (браузер)
    participant D as Django
    participant F as FastAPI
    actor E as Роботодавець
    K->>D: GET /cabinet/ws-token/ (сесія)
    D-->>K: {url, JWT role=candidate, candidate_id}
    K->>F: WebSocket /ws/applications/{id}?token=…
    F-->>K: поточні статуси (історія)
    E->>D: POST /api/applications/{id}/status/
    D->>F: POST /applications/status (сервісний JWT)
    F-->>K: {"type":"application_status","status":"interview",…}
```

## Автентифікація між сервісами

* Спільний секрет `SHARED_JWT_SECRET` (змінна середовища, не в репозиторії), алгоритм HS256.
* Django підписує **сервісний JWT** (`iss=hirehub-django`, `role=service`, TTL 5 хв) для кожного запиту.
* Для WebSocket Django видає **короткоживучий токен кандидата** (`role=candidate`, `candidate_id`, TTL 10 хв):
  він не дає доступу до `/match/*`, лише до власного потоку статусів.
* Користувачі FastAPI (`admin`, `service`, `viewer`) мають власні паролі (bcrypt) і отримують токени через `/auth/token`.

## Що, якщо сервіс підбору недоступний

Збереження вакансій і профілів **не залежить** від FastAPI: синхронізація виконується після коміту, помилки логуються
й повторюються з відступом (Celery); сторінки показують порожній блок рекомендацій. Періодичне завдання
`integration.tasks.reindex_all` (щогодини) і команда `manage.py reindex_matching` відновлюють індекс.
