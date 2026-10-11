"""Безпека: хешування паролів (bcrypt), JWT доступу (HS256), OAuth2PasswordBearer, ролі.

Два типи токенів з одним секретом:
  * токени, виданні цим сервісом (/auth/token): iss=hirehub-matching, користувач існує в БД;
  * токени Django (iss=hirehub-django): сервісний (role=service) і короткоживучий токен кандидата
    для WebSocket (role=candidate, claim candidate_id) — підписує Django спільним секретом.
"""
import time
from dataclasses import dataclass, field

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.db.session import get_session

ISSUER_SELF = 'hirehub-matching'
ISSUER_DJANGO = 'hirehub-django'

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='auth/token')


def hash_password(password: str) -> str:
    rounds = get_settings().bcrypt_rounds
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def create_access_token(subject: str, role: str, *, minutes: int | None = None, extra: dict | None = None,
                        issuer: str = ISSUER_SELF) -> str:
    settings = get_settings()
    now = int(time.time())
    lifetime = (minutes if minutes is not None else settings.access_token_minutes) * 60
    payload = {'sub': subject, 'role': role, 'iss': issuer, 'iat': now, 'exp': now + lifetime, **(extra or {})}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm],
                          options={'require': ['exp', 'sub', 'role']})
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError('Термін дії токена минув.') from exc
    except jwt.PyJWTError as exc:
        raise UnauthorizedError('Недійсний токен.') from exc


@dataclass
class Principal:
    username: str
    role: str
    user_id: int | None = None
    claims: dict = field(default_factory=dict)


async def principal_from_token(token: str, session: AsyncSession) -> Principal:
    from app.repositories.users import UserRepository  # уникаємо циклічного імпорту

    claims = decode_token(token)
    if claims.get('iss') == ISSUER_DJANGO:
        if claims['role'] == 'service':
            return Principal(username=claims['sub'], role='service', claims=claims)
        if claims['role'] == 'candidate' and isinstance(claims.get('candidate_id'), int):
            # короткоживучий токен кандидата для WebSocket: дає доступ лише до його власних статусів
            return Principal(username=claims['sub'], role='candidate', claims=claims)
        raise ForbiddenError('Токен Django має містити роль service або candidate.')
    # токен цього сервісу: користувач має існувати й бути активним; роль беремо з БД, а не з токена
    user = await UserRepository(session).get_by_username(claims['sub'])
    if user is None or not user.is_active:
        raise UnauthorizedError('Користувача не знайдено або вимкнено.')
    return Principal(username=user.username, role=user.role, user_id=user.id, claims=claims)


async def get_principal(token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)) -> Principal:
    return await principal_from_token(token, session)


def require_roles(*roles: str):
    """Залежність: дозволяє лише вказані ролі, інакше 403."""
    async def checker(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise ForbiddenError(f'Потрібна одна з ролей: {", ".join(roles)}.')
        return principal
    return checker
