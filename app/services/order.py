from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ItemNotFoundError, NotEnoughItemsError, OrderNotFoundError, OrderCantBeCancelledError, \
    OrderCantBePaidError, OrderCantBeCompletedError
from app.models.models import Orders, ItemsOrders, Users
from app.repositories.item import ItemRepository
from app.repositories.order import OrderRepository
from app.repositories.user import UserRepository
from app.schemas.order import OrderCreate, OrderItemCreate


class OrderService:
    def __init__(self, session):
        self.session = session
        self.order_repo = OrderRepository(session)
        self.items_repo = ItemRepository(session)
        self.user_repo = UserRepository(session)

    async def create_order(self, user_id: UUID, order: OrderCreate) -> Orders:
        amount = Decimal(0)
        order_items: list[ItemsOrders] = []
        try:
            for item_order in sorted(order.items, key=lambda position: position.item_id):
                item = await self.items_repo.get_by_id(item_order.item_id)
                if not item:
                    raise ItemNotFoundError("Item not found")
                order_items.append(ItemsOrders(quantity=item_order.quantity, price=item.price, item_id=item.id))
                amount += item.price * item_order.quantity
                await self.items_repo.sub_item_stock(item_order.item_id, item_order.quantity)

            order = await self.order_repo.create(amount, user_id, order_items)
            await self.session.commit()
            return order
        except (NotEnoughItemsError, IntegrityError, ItemNotFoundError):
            await self.session.rollback()
            raise

    async def get_order_by_id(self, order_id: UUID, user: Users) -> Orders | None:
        order = await self.order_repo.get_by_id(order_id)
        if not order or order.user_id != user.id and not user.is_admin:
            return None
        return order

    async def get_orders(self, user: Users, page: int, limit: int) -> list[Orders]:
        if not user.is_admin:
            orders = await self.order_repo.get_orders_by_id(user.id, (page - 1) * limit, limit)
        else:
            orders = await self.order_repo.get_all_orders((page - 1) * limit, limit)
        return orders

    async def cancel_order(self, order_id: UUID, user: Users) -> Orders:
        try:
            order = await self.order_repo.get_by_id_for_update(order_id)
            if not order or order.user_id != user.id and not user.is_admin:
                raise OrderNotFoundError("Order not found")

            if order.status != "created":
                raise OrderCantBeCancelledError("Order cannot be canceled")
            await self.order_repo.cancel_order(order_id)

            for item in sorted(order.items, key=lambda position: position.item_id):
                await self.items_repo.add_item_stock(item.item_id, item.quantity)
            await self.session.commit()
            return order
        except Exception:
            await self.session.rollback()
            raise

    async def pay_order(self, order_id: UUID, user: Users) -> Orders:
        try:
            order = await self.order_repo.get_by_id_for_update(order_id)
            if not order or order.user_id != user.id and not user.is_admin:
                raise OrderNotFoundError("Order not found")
            if order.status == "paid":
                return order
            if order.status != "created":
                raise OrderCantBePaidError("Order cannot be paid")
            await self.order_repo.pay_order(order_id)
            await self.session.commit()
            return order
        except Exception:
            await self.session.rollback()
            raise


    async def complete_order(self, order_id: UUID) -> Orders:
        try:
            order = await self.order_repo.get_by_id_for_update(order_id)
            if not order:
                raise OrderNotFoundError("Order not found")
            if order.status == "completed":
                await self.session.commit()
                return order
            if order.status != "paid":
                raise OrderCantBeCompletedError("Order cannot be completed")

            await self.order_repo.complete_order(order_id)
            await self.session.commit()
            return order
        except Exception:
            await self.session.rollback()
            raise
