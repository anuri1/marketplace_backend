from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CategoryAlreadyExitstsError, UserAlreadyExitstsError, CategoryNotFoundError
from app.models.models import Items, Categories
from app.repositories.item import ItemRepository
from app.schemas.item import ItemCreate, CategoryCreate


class ItemService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.item_repo = ItemRepository(self.session)

    async def get_by_id(self, item_id: UUID) -> Items | None:
        return await self.item_repo.get_by_id(item_id)

    async def get_list(self, page: int, limit: int) -> list[Items]:
        return await self.item_repo.get_list((page - 1) * limit, limit)

    async def create(self, item: ItemCreate) -> Items:
        if item.category_id and not await self.item_repo.get_category_by_id(item.category_id):
            raise CategoryNotFoundError("Category does not exist")

        try:
            item = await self.item_repo.create(**item.model_dump())
            await self.session.commit()
            return item
        except IntegrityError:
            await self.session.rollback()
            if item.category_id and await self.item_repo.get_category_by_id(item.category_id):
                raise UserAlreadyExitstsError("User already exists")
            raise

    async def get_category_by_id(self, category_id: UUID) -> Categories | None:
        return await self.item_repo.get_category_by_id(category_id)

    async def get_categories(self, page: int, limit: int) -> list[Categories]:
        categories = await self.item_repo.get_category_list((page - 1) * limit, limit)
        return categories

    async def create_category(self, category: CategoryCreate) -> Categories:
        if await self.item_repo.get_category_by_name(category.name):
            raise CategoryAlreadyExitstsError(f"Category {category.name} already exists")

        try:
            category = await self.item_repo.create_category(**category.model_dump())
            await self.session.commit()
            return category
        except IntegrityError:
            await self.session.rollback()
            raise

