"""Налаштування сервісу через pydantic-settings (змінні середовища / .env). Секретів у коді немає."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_prefix='MATCHING_', extra='ignore')

    app_name: str = 'HireHub Matching Service'
    # префікс, під яким сервіс видно за reverse proxy (nginx: /matching); потрібен лише для /docs і OpenAPI
    root_path: str = ''
    database_url: str = 'sqlite+aiosqlite:///./matching.db'
    # Спільний секрет JWT із Django. Назва змінної без префікса — така сама, як у Django.
    jwt_secret: str = Field(default='dev-shared-jwt-secret-change-me-32chars', validation_alias='SHARED_JWT_SECRET')
    jwt_algorithm: str = 'HS256'
    access_token_minutes: int = 60
    cors_origins: list[str] = ['http://localhost:8080', 'http://127.0.0.1:8080', 'http://127.0.0.1:8005']
    # у dev/тестах таблиці створюються автоматично; у Docker — лише через Alembic
    auto_create_tables: bool = False
    admin_username: str = ''
    admin_password: str = ''
    ws_max_connections_per_candidate: int = 5
    bcrypt_rounds: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
