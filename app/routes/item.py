from typing import List, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CategoryAlreadyExitstsError, CategoryNotFoundError
from app.db.session import get_session
from app.dependencies.auth import check_user_is_admin
from app.schemas.item import ItemRead, ItemCreate, CategoryRead, CategoryCreate
from app.services.item import ItemService

item_router = APIRouter(prefix="/item", tags=["item"])


@item_router.get("/items", response_model=List[ItemRead])
async def get_page(
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(le=20, ge=1)] = 5,
        session: AsyncSession = Depends(get_session)
):
    item_service = ItemService(session)
    items = await item_service.get_list(page, limit)
    return items


@item_router.get("/categories", response_model=List[CategoryRead])
async def get_categories(
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(le=20, ge=1)] = 5,
        session: AsyncSession = Depends(get_session)
):
    item_service = ItemService(session)
    categories = await item_service.get_categories(page, limit)
    return categories


@item_router.post(
    "/category/create",
    response_model=CategoryRead,
    dependencies=[Depends(check_user_is_admin)],
    status_code=status.HTTP_201_CREATED
)
async def create_category(category: CategoryCreate, session: AsyncSession = Depends(get_session)):
    item_service = ItemService(session)
    try:
        category = await item_service.create_category(category)
    except CategoryAlreadyExitstsError:
        raise HTTPException(status_code=400, detail="Category already exists")
    return category


@item_router.post(
    "/create",
    response_model=ItemRead,
    dependencies=[Depends(check_user_is_admin)],
    status_code=status.HTTP_201_CREATED
)
async def create_item(item: ItemCreate, session: AsyncSession = Depends(get_session)):
    item_service = ItemService(session)
    try:
        item = await item_service.create(item)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Invalid item data")
    except CategoryNotFoundError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found")
    return item


@item_router.get("/{item_id}", response_model=ItemRead)
async def read_item(item_id: UUID, session: AsyncSession = Depends(get_session)):
    item_service = ItemService(session)
    item = await item_service.get_by_id(item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return item
