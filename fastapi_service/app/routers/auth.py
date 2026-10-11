from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, get_principal, require_roles
from app.db.session import get_session
from app.schemas.auth import AdminCreateUserIn, RegisterIn, Role, TokenOut, UserOut
from app.services.auth import AuthService

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/register', response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterIn, session: AsyncSession = Depends(get_session)):
    """Публічна реєстрація: завжди створює користувача з роллю viewer (лише читання підбору)."""
    return await AuthService(session).register(data.username, data.password, Role.viewer.value)


@router.post('/token', response_model=TokenOut)
async def token(form: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(get_session)):
    """OAuth2 Password flow: username + password → JWT доступу."""
    return await AuthService(session).login(form.username, form.password)


@router.get('/me', response_model=UserOut)
async def me(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    from app.repositories.users import UserRepository
    user = await UserRepository(session).get_by_username(principal.username)
    if user is None:   # сервісний токен Django не має запису в БД
        return UserOut(id=0, username=principal.username, role=Role(principal.role), is_active=True)
    return user


@router.post('/users', response_model=UserOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_roles('admin'))])
async def create_user(data: AdminCreateUserIn, session: AsyncSession = Depends(get_session)):
    """Створення користувача з будь-якою роллю — лише адміністратор."""
    return await AuthService(session).register(data.username, data.password, data.role.value)
