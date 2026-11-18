from datetime import datetime
import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Enum as SQLEnum, String, func, ForeignKey, CheckConstraint, UniqueConstraint, DateTime, Text, \
    Numeric, Index, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.enums import OrderStatuses

from app.db.base import Base

order_statuses = SQLEnum(OrderStatuses, name="order_statuses")


class IdMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Users(IdMixin, Base):
    __tablename__ = "users"

    login: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_admin: Mapped[bool] = mapped_column(nullable=False, server_default=false())

    orders: Mapped[list["Orders"]] = relationship(back_populates="user", passive_deletes=True)


class Items(IdMixin, Base):
    __tablename__ = "items"

    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(default=0, nullable=False)

    category_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    category: Mapped["Categories | None"] = relationship(back_populates="items")

    orders: Mapped[list["ItemsOrders"]] = relationship(back_populates="item", passive_deletes=True)

    __table_args__ = (
        CheckConstraint("price >= 0", name="item_price_check"),
        CheckConstraint("stock >= 0", name="stock_check"),
        Index("idx_category_id", "category_id"),
    )


class Categories(IdMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)

    items: Mapped[list["Items"]] = relationship(back_populates="category", passive_deletes=True)


class Orders(IdMixin, Base):
    __tablename__ = "orders"

    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[OrderStatuses] = mapped_column(
        order_statuses, default=OrderStatuses.created, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    user: Mapped["Users"] = relationship(back_populates="orders")

    items: Mapped[list["ItemsOrders"]] = relationship(
        back_populates="order", passive_deletes=True
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="amount_check"),
        Index("idx_user_id", "user_id"),
    )



class ItemsOrders(IdMixin, Base):
    __tablename__ = "items_orders"

    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    order: Mapped["Orders"] = relationship(back_populates="items")

    item_id: Mapped[UUID] = mapped_column(ForeignKey("items.id", ondelete="RESTRICT"))
    item: Mapped["Items"] = relationship(back_populates="orders")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_check"),
        CheckConstraint("price >= 0", name="itemsorder_price_check"),
        UniqueConstraint("order_id", "item_id", name="order_id_item_id_unique"),
        Index("idx_order_id", "order_id"),
    )
