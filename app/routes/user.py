from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExitstsError
from app.core.security import create_access_token, get_user_id_from_token
from app.db.session import get_session
from app.dependencies.auth import get_current_user
from app.schemas.user import UserCreate, UserRead, UserLogin
from app.services.user import UserService

user_router = APIRouter(prefix="/user", tags=["user"])


@user_router.post("/register", response_model=UserRead, status_code=201)
async def create_user(user: UserCreate, session: AsyncSession = Depends(get_session)):
    user_service = UserService(session=session)
    try:
        return await user_service.register(user)
    except UserAlreadyExitstsError:
        raise HTTPException(status_code=409, detail="User or email already exists")


@user_router.post("/login", response_model=UserRead)
async def login(response: Response, credentials: UserLogin, session: AsyncSession = Depends(get_session)):
    user_service = UserService(session=session)
    result = await user_service.check_user_credentials(credentials.login, credentials.password)
    if not result:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": str(result.id)})
    response.set_cookie("token", token, httponly=True)
    return result


@user_router.get("/me", response_model=UserRead)
async def get_me(user: UserRead = Depends(get_current_user)):
    return user


@user_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("token")
    return {"msg": f"logged out"}
