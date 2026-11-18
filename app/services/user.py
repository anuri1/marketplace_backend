from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UserAlreadyExitstsError
from app.core.security import get_password_hash, verify_password
from app.models.models import Users
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRead


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(self.session)

    async def register(self, user: UserCreate) -> Users:
        if await self.user_repo.get_by_email(user.email) or await self.user_repo.get_by_login(user.login):
            raise UserAlreadyExitstsError("User already exists")
        try:
            hashed_password = get_password_hash(user.password)
            created_user = await self.user_repo.create(login=user.login, email=user.email, hashed_password=hashed_password)
            await self.session.commit()
            return created_user
        except IntegrityError:
            await self.session.rollback()
            if await self.user_repo.get_by_email(user.email) or await self.user_repo.get_by_login(user.login):
                raise UserAlreadyExitstsError("User already exists")
            raise

    async def check_user_credentials(self, login: str, password: str) -> UserRead | None:
        user = await self.user_repo.get_by_login(login)
        if not user:
            return None
        return UserRead.model_validate(user) if verify_password(password, user.hashed_password) else None

    async def get_user(self, user_id: UUID) -> Users | None:
        user = await self.user_repo.get_by_id(user_id)
        return user
