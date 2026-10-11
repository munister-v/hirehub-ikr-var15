from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    admin = 'admin'
    service = 'service'
    viewer = 'viewer'


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r'^[A-Za-z0-9_.-]+$')
    password: str = Field(min_length=8, max_length=72)


class AdminCreateUserIn(RegisterIn):
    role: Role = Role.viewer


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: Role
    is_active: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int
    role: Role
