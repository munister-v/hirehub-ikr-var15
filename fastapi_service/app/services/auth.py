from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.repositories.users import UserRepository
from app.schemas.auth import TokenOut


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.users = UserRepository(session)

    async def register(self, username: str, password: str, role: str = 'viewer') -> User:
        if await self.users.get_by_username(username):
            raise ConflictError('Користувач із таким іменем уже існує.')
        user = await self.users.create(username, hash_password(password), role)
        await self.session.commit()
        return user

    async def login(self, username: str, password: str) -> TokenOut:
        user = await self.users.get_by_username(username)
        # однакове повідомлення для «немає користувача» й «хибний пароль» — не розкриваємо, що саме не так
        if user is None or not user.is_active or not verify_password(password, user.hashed_password):
            raise UnauthorizedError('Хибне ім’я користувача або пароль.')
        minutes = get_settings().access_token_minutes
        token = create_access_token(user.username, user.role, minutes=minutes)
        return TokenOut(access_token=token, expires_in=minutes * 60, role=user.role)

    async def ensure_admin(self, username: str, password: str) -> None:
        """Створює адміністратора зі змінних середовища (якщо його ще немає)."""
        if username and password and not await self.users.get_by_username(username):
            await self.users.create(username, hash_password(password), 'admin')
            await self.session.commit()
