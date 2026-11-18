from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update

from app.core.exceptions import ItemNotFoundError, NotEnoughItemsError
from app.models.models import Items, Categories
from app.repositories.base import BaseRepository
from app.schemas.item import ItemCreate


class ItemRepository(BaseRepository):
    async def get_by_id(self, item_id: UUID) -> Items | None:
        item = await self.session.get(Items, item_id)
        return item

    async def get_list(self, offset: int, limit: int) -> list[Items]:
        result = await self.session.execute(
            select(Items)
            .order_by(Items.id)
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars())

    async def create(
        self,
        name: str,
        description: str | None,
        price: Decimal,
        stock: int,
        category_id: UUID | None = None,
    ) -> Items:
        item = Items(name=name, description=description, price=price, stock=stock, category_id=category_id)
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_category_by_id(self, category_id: UUID) -> Categories | None:
        category = await self.session.get(Categories, category_id)
        return category


    async def get_category_by_name(self, name: str) -> Categories | None:
        category = await self.session.execute(
            select(Categories)
            .where(Categories.name == name)
        )
        return category.scalar_one_or_none()


    async def get_category_list(self, offset: int, limit: int) -> list[Categories]:
        categories = await self.session.execute(
            select(Categories)
            .order_by(Categories.id)
            .offset(offset)
            .limit(limit)
        )
        return list(categories.scalars())

    async def create_category(self, name: str) -> Categories:
        category = Categories(name=name)
        self.session.add(category)
        await self.session.flush()
        return category

    async def sub_item_stock(self, item_id: UUID, val: int):
        if val <= 0:
            raise ValueError("Quantity must be positive")

        item = await self.get_by_id(item_id)
        if not item:
            raise ItemNotFoundError("Item not found")

        item = await self.session.execute(
            update(Items)
            .where(
                Items.id == item_id,
                Items.stock >= val,
                   )
            .values(stock=(Items.stock - val))
            .returning(Items.id)
        )
        if item.scalar_one_or_none() is None:
            raise NotEnoughItemsError("Not enough stock")

    async def add_item_stock(self, item_id: UUID, val: int):
        if val <= 0:
            raise ValueError("Quantity must be positive")

        item = await self.get_by_id(item_id)
        if not item:
            raise ItemNotFoundError("Item not found")

        await self.session.execute(
            update(Items)
            .where(Items.id == item_id)
            .values(stock=(Items.stock + val))
        )
