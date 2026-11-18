from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.enums import OrderStatuses
from app.models.models import Orders, ItemsOrders
from app.repositories.base import BaseRepository
from app.schemas.item import ItemCreate
from app.schemas.order import OrderItemCreate


class OrderRepository(BaseRepository):
    async def create(self, amount: Decimal, user_id: UUID, items: list[ItemsOrders]) -> Orders:
        order = Orders(amount=amount, user_id=user_id, items=items)
        self.session.add(order)
        await self.session.flush()
        return order

    async def get_by_id(self, order_id: UUID) -> Orders | None:
        result = await self.session.execute(
            select(Orders)
            .where(Orders.id == order_id)
            .options(selectinload(Orders.items))
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, order_id: UUID) -> Orders | None:
        result = await self.session.execute(
            select(Orders)
            .where(Orders.id == order_id)
            .with_for_update()
            .options(selectinload(Orders.items))
        )
        return result.scalar_one_or_none()

    async def get_orders_by_id(self, user_id: UUID, offset: int, limit: int) -> list[Orders]:
        result = await self.session.execute(
            select(Orders)
            .where(Orders.user_id == user_id)
            .order_by(Orders.created_at.desc(), Orders.id)
            .offset(offset)
            .limit(limit)
            .options(selectinload(Orders.items))
        )
        return list(result.scalars())

    async def get_all_orders(self, offset: int, limit: int) -> list[Orders]:
        result = await self.session.execute(
            select(Orders)
            .order_by(Orders.created_at.desc(), Orders.id)
            .offset(offset)
            .limit(limit)
            .options(selectinload(Orders.items))
        )
        return list(result.scalars())

    async def cancel_order(self, order_id: UUID) -> Orders | None:
        order = await self.session.execute(
            update(Orders)
            .where(Orders.id == order_id)
            .values(status=OrderStatuses.cancelled)
            .returning(Orders)
        )
        return order.scalar_one_or_none()

    async def pay_order(self, order_id: UUID) -> Orders | None:
        order = await self.session.execute(
            update(Orders)
            .where(Orders.id == order_id)
            .values(status=OrderStatuses.paid)
            .returning(Orders)
        )
        return order.scalar_one_or_none()

    async def complete_order(self, order_id: UUID) -> Orders | None:
        order = await self.session.execute(
            update(Orders)
            .where(Orders.id == order_id)
            .values(status=OrderStatuses.completed)
            .returning(Orders)
        )
        return order.scalar_one_or_none()
