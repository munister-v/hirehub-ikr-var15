"""Точка входу FastAPI: Matching Service (варіант 15) — підбір вакансій і кандидатів за навичками."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.db.base import Base
from app.db.session import dispose_engine, get_engine, session_factory
from app.routers import applications, auth, health, index, match
from app.services.auth import AuthService
from app.services.notifications import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = get_engine()
    if settings.auto_create_tables:       # dev і тести; у Docker схему створює Alembic
        from app import models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    async with session_factory()() as session:
        await AuthService(session).ensure_admin(settings.admin_username, settings.admin_password)
    app.state.ws_manager = ConnectionManager(settings.ws_max_connections_per_candidate)
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version='1.0.0',
        root_path=settings.root_path,
        description='Підбір відповідностей вакансій і кандидатів за навичками (коефіцієнт Жаккара / косинусна '
                    'подібність). Індекс оновлюється сервісом Django по HTTP; статуси заявок надходять по WebSocket.',
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=['*'], allow_headers=['*'])
    register_error_handlers(app)
    for module in (health, auth, index, match, applications):
        app.include_router(module.router)
    return app


app = create_app()
