# Додаток А. Контрольний перелік перед захистом

Статуси: ✔ виконано й перевірено · ◐ виконано частково · ✖ не виконувалось. Перевірка проведена 11.10.2026.

| № | Пункт | Статус | Підтвердження |
|---|---|---|---|
| 1 | README, `.env.example`, `.gitignore`; секрети відсутні | ✔ | `README.md`, `.env.example`; `.env` у `.gitignore`, у `git ls-files` його немає |
| 2 | `docker compose up --build` піднімає django, fastapi, postgres, redis, nginx без ручних кроків | ✔ | перевірено в Docker (Colima, macOS): усі 7 сервісів `healthy`, див. `docs/compose-ps.txt`; сайт — `:8080` |
| 3 | Міграції Django і Alembic застосовуються автоматично; БД наповнюється даними | ✔ | `django_app/entrypoint.sh` (migrate, seed_demo, reindex), `fastapi_service/entrypoint.sh` (`alembic upgrade head`); `/matching/index/stats` → 18 вакансій, 10 кандидатів |
| 4 | Django: ≥ 6 моделей зі зв'язками 1:N, M:N, 1:1 | ✔ | 11 моделей: `jobs/models.py`, `docs/er-django.md` |
| 5 | Адмін-панель налаштована; у списках немає N+1 | ✔ | `jobs/admin.py` (`list_select_related`, inlines, фільтри, пошук); тести кількості запитів |
| 6 | Реєстрація, вхід, ролі та обмеження доступу у Django, DRF, FastAPI | ✔ | `accounts/`, `api/permissions.py`, `app/core/security.py`; тести прав у `tests/test_web.py`, `tests/test_api.py`, `tests/test_auth.py` |
| 7 | ≥ 8 ендпоінтів DRF і ≥ 8 ендпоінтів FastAPI; працюють Swagger UI / ReDoc | ✔ | DRF — 7 ресурсів і 3 дії (`README.md`); FastAPI — 16 HTTP-шляхів + WebSocket; скріншоти `07`, `08`, `11`, `12` |
| 8 | FastAPI має WebSocket і/або BackgroundTasks; міжсервісна взаємодія працює й автентифікована | ✔ | WebSocket `/ws/applications/{id}`, `BackgroundTasks` у `/index/reindex`; сервісний JWT; перевірено наскрізно (статус заявки → повідомлення в браузері через nginx) |
| 9 | Тести проходять; покриття ≥ 70 %; є тест кількості SQL-запитів і тест взаємодії сервісів | ✔ | Django 57 тестів, покриття 92 %; FastAPI 34 тести, покриття 95 %; `test_list_query_count_does_not_grow_with_data`, `tests/test_integration.py` |
| 10 | CI запускає лінтер, тести та збірку образів | ◐ | `.github/workflows/ci.yml` підготовлено й узгоджено з локальними командами; на GitHub не запускався (репозиторій не публікувався) |
| 11 | Є ER-діаграми, схема взаємодії, колекція Postman, порівняльний аналіз Django і FastAPI | ✔ | `docs/er-*.md`, `docs/architecture.md`, `docs/postman/…`, `docs/comparison-django-vs-fastapi.md` |
| 12 | Історія Git ≥ 15 змістовних комітів; гілки, злиття через PR | ✔ | `git log --oneline` (понад 25 комітів, 8 гілок `feature/*`); 8 pull request-ів у [munister-v/hirehub-ikr-var15](https://github.com/munister-v/hirehub-ikr-var15/pulls) |

## Не виконувалось (чесно)

* **Злиття pull request-ів на GitHub** — PR #1–#8 відкрито «ланцюжком» (кожен базується на попередній гілці), але не злито:
  це робиться кнопкою *Merge* у порядку #1 → #8 або командою `gh pr merge`.
* **Навантажувальний тест Locust** — файл `docs/locustfile.py` підготовлено, але не запускався (необов'язковий пункт).
* **ЛР №16 (розгортання на PaaS)** — не виконувалось.
* **Підвищена складність (за бажанням):** реалізовано лише «Пояснення відповідності» (`/match/explain`).

> Репозиторій: https://github.com/munister-v/hirehub-ikr-var15. Приватний репозиторій створити не вдалося (обмеження акаунта на стороні GitHub), тому репозиторій публічний.
