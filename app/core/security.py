from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from jose import jwt, JWTError
from pwdlib import PasswordHash

from app.core.config import auth_settings

password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=auth_settings.expires_in_days)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, auth_settings.secret_key, algorithm=auth_settings.algorithm)
    return encoded_jwt


def get_user_id_from_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, auth_settings.secret_key, algorithms=[auth_settings.algorithm])
        return UUID(payload.get("sub", None))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен"
        )
