from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


class UserRepository:
    """Шар репозиторіїв: уся робота з таблицею users — тут; сервіси про SQL не знають."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_username(self, username: str) -> User | None:
        return (await self.session.execute(select(User).where(User.username == username))).scalar_one_or_none()

    async def create(self, username: str, hashed_password: str, role: str) -> User:
        user = User(username=username, hashed_password=hashed_password, role=role)
        self.session.add(user)
        await self.session.flush()
        return user

    async def count(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(User))).scalar_one()
