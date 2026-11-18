from typing import List, Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotEnoughItemsError, ItemNotFoundError, OrderNotFoundError, OrderCantBeCancelledError, \
    OrderCantBePaidError, OrderCantBeCompletedError
from app.db.session import get_session
from app.dependencies.auth import get_current_user, check_user_is_admin
from app.models.models import Users
from app.schemas.order import OrderCreate, OrderRead
from app.schemas.user import UserRead
from app.services.order import OrderService

order_router = APIRouter(prefix="/order", tags=["order"])


@order_router.post("/create", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
        order: OrderCreate,
        session: AsyncSession = Depends(get_session),
        user: Users = Depends(get_current_user)
):
    order_service = OrderService(session)
    try:
        order = await order_service.create_order(user.id, order)
        return order
    except NotEnoughItemsError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough items")
    except ItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")


@order_router.get("/orders", response_model=List[OrderRead])
async def get_orders(
        page: Annotated[int, Query(ge=1)] = 1,
        limit: Annotated[int, Query(ge=1, le=20)] = 5,
        session: AsyncSession = Depends(get_session),
        user: Users = Depends(get_current_user)
):
    order_service = OrderService(session)
    orders = await order_service.get_orders(user, page, limit)
    return orders


@order_router.patch("/{order_id}/cancel", response_model=OrderRead, status_code=status.HTTP_200_OK)
async def cancel_order(order_id: UUID, session: AsyncSession = Depends(get_session), user: Users = Depends(get_current_user)):
    order_service = OrderService(session)
    try:
        cancelled_order = await order_service.cancel_order(order_id, user)
    except OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except OrderCantBeCancelledError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order cannot be canceled")
    return cancelled_order

@order_router.patch("/{order_id}/pay", response_model=OrderRead, status_code=status.HTTP_200_OK)
async def pay_order(order_id: UUID, session: AsyncSession = Depends(get_session), user: Users = Depends(get_current_user)):
    order_service = OrderService(session)
    try:
        order = await order_service.pay_order(order_id, user)
    except OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except OrderCantBePaidError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order cannot be paid")
    return order


@order_router.patch(
    "/{order_id}/complete",
    response_model=OrderRead,
    dependencies=[Depends(check_user_is_admin)],
    status_code=status.HTTP_200_OK)
async def complete_order(order_id: UUID, session: AsyncSession = Depends(get_session)):
    order_service = OrderService(session)
    try:
        order = await order_service.complete_order(order_id)
    except OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except OrderCantBeCompletedError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order cannot be completed")
    return order



@order_router.get("/{order_id}", response_model=OrderRead, status_code=status.HTTP_200_OK)
async def read_order(order_id: UUID, session: AsyncSession = Depends(get_session), user: Users = Depends(get_current_user)):
    order_service = OrderService(session)
    order = await order_service.get_order_by_id(order_id, user)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
