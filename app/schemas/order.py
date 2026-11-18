from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from app.models.enums import OrderStatuses
from app.schemas.base import CreateModel, ReadModel


class OrderItemCreate(CreateModel):
    item_id: UUID
    quantity: int = Field(ge=1)


class OrderItemRead(ReadModel):
    id: UUID
    item_id: UUID
    quantity: int
    price: Decimal


class OrderCreate(CreateModel):
    items: list[OrderItemCreate] = Field(min_length=1)

    @field_validator("items")
    @classmethod
    def check_items_only_unique(cls, v):
        ids = [item.item_id for item in v]
        if len(set(ids)) != len(ids):
            raise ValueError("there must be no duplicate items")
        return v


class OrderRead(ReadModel):
    id: UUID
    amount: Decimal
    status: OrderStatuses
    created_at: datetime
    items: list[OrderItemRead]
