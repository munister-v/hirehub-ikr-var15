# ER-діаграма FastAPI-сервісу (PostgreSQL `hirehub_matching`)

Сервіс має **власну** БД. Прямого доступу до БД Django немає: дані потрапляють лише через HTTP (`/index/*`).
Ідентифікатори `indexed_vacancies.id` та `indexed_candidates.id` дорівнюють id у Django (не автоінкремент).

```mermaid
erDiagram
    INDEXED_VACANCIES ||--o{ VACANCY_SKILLS : "CASCADE"
    INDEXED_CANDIDATES ||--o{ CANDIDATE_SKILLS : "CASCADE"

    USERS {
        int id PK
        string username UK
        string hashed_password "bcrypt"
        string role "admin|service|viewer"
        bool is_active
    }
    INDEXED_VACANCIES {
        int id PK "= vacancy.id у Django"
        string title
        string company
        string city
        int salary_min
        int salary_max
    }
    VACANCY_SKILLS {
        int vacancy_id FK
        string skill_key "нормалізовано, індекс"
        int level
    }
    INDEXED_CANDIDATES {
        int id PK "= candidate.id у Django"
        string full_name
        string headline
    }
    CANDIDATE_SKILLS {
        int candidate_id FK
        string skill_key "нормалізовано, індекс"
        int level
    }
    APPLICATION_EVENTS {
        int id PK
        int application_id "індекс"
        int candidate_id "індекс"
        string status
    }
    INDEX_JOBS {
        string id PK "uuid"
        string status "pending|running|done|failed"
    }
```
