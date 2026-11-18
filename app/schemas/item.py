from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.schemas.base import CreateModel, ReadModel


class ItemCreate(CreateModel):
    name: str = Field(min_length=1, max_length=256)
    description: str | None = None
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    stock: int = Field(ge=0)
    category_id: UUID | None = None


class ItemRead(ReadModel):
    id: UUID
    name: str
    description: str | None
    price: Decimal
    stock: int
    category_id: UUID | None


class CategoryCreate(CreateModel):
    name: str = Field(min_length=1, max_length=256)


class CategoryRead(ReadModel):
    id: UUID
    name: str
