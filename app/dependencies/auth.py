from typing import Annotated

from fastapi import Depends, Cookie, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_user_id_from_token
from app.db.session import get_session
from app.models.models import Users
from app.schemas.user import UserRead
from app.services.user import UserService


async def get_current_user(
        token: Annotated[str | None, Cookie()] = None,
        session: AsyncSession = Depends(get_session)
) -> Users:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    user_service = UserService(session=session)

    user_id = get_user_id_from_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user


async def check_user_is_admin(current_user: Users = Depends(get_current_user)) -> Users:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return current_user
