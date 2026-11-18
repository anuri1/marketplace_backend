from datetime import datetime
from uuid import UUID

from pydantic import EmailStr, Field

from app.schemas.base import CreateModel, ReadModel


class UserCreate(CreateModel):
    login: str = Field(min_length=3, max_length=50)
    email: EmailStr = Field(max_length=256)
    password: str = Field(min_length=8, max_length=128)


class UserRead(ReadModel):
    id: UUID
    login: str
    email: EmailStr
    registered_at: datetime


class UserLogin(CreateModel):
    login: str
    password: str
