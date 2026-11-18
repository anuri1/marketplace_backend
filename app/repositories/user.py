from uuid import UUID

from sqlalchemy import select

from app.models.models import Users
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    async def get_by_login(self, login: str) -> Users | None:
        result = await self.session.execute(
            select(Users)
            .where(Users.login == login)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Users | None:
        result = await self.session.execute(
            select(Users)
            .where(Users.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> Users | None:
        return await self.session.get(Users, user_id)

    async def create(self, login: str, email: str, hashed_password: str) -> Users:
        user = Users(login=login, email=email, hashed_password=hashed_password)
        self.session.add(user)
        await self.session.flush()
        return user
