from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

import pytest
from jose import jwt
from sqlalchemy import func, select

from app.core.config import auth_settings
from app.core.security import verify_password
from app.models.models import Users


@pytest.mark.asyncio
async def test_register(client, session_factory):
    response = await client.post(
        "/user/register",
        json={
            "login": "test_user",
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["login"] == "test_user"
    assert data["email"] == "test@example.com"
    assert "id" in data
    assert "password" not in data
    assert "hashed_password" not in data
    async with session_factory() as session:
        user = await session.get(Users, UUID(data["id"]))
        assert user is not None
        assert user.is_admin is False
        assert user.hashed_password != "password123"
        assert verify_password("password123", user.hashed_password)
        assert not verify_password("wrong-password", user.hashed_password)


@pytest.mark.asyncio
async def test_the_same_register_data(client):
    user = {
        "login": "test_user",
        "email": "test@example.com",
        "password": "password123",
    }
    response = await client.post(
        "/user/register",
        json=user
    )
    response2 = await client.post(
        "/user/register",
        json=user
    )

    assert response.status_code == 201
    assert response2.status_code == 409


@pytest.mark.asyncio
async def test_login_and_get_me(client, registered_user):
    before_login = datetime.now(timezone.utc)
    response_login = await client.post(
        "/user/login",
        json={
            "login": registered_user["login"],
            "password": "password123",
        }
    )

    assert response_login.status_code == 200

    assert response_login.json()["id"] == registered_user["id"]
    assert "token" in response_login.cookies
    assert "hashed_password" not in response_login.json()
    assert "password" not in response_login.json()

    token = response_login.cookies["token"]
    payload = jwt.decode(
        token, auth_settings.secret_key, algorithms=[auth_settings.algorithm]
    )
    assert payload["sub"] == registered_user["id"]
    lifetime = timedelta(days=auth_settings.expires_in_days)
    assert int((before_login + lifetime).timestamp()) <= payload["exp"]
    assert payload["exp"] <= int((datetime.now(timezone.utc) + lifetime).timestamp())
    assert "password" not in payload
    assert "hashed_password" not in payload
    assert "httponly" in response_login.headers["set-cookie"].lower()

    response_me = await client.get(
        "/user/me",
    )

    assert response_me.status_code == 200
    assert response_me.json() == response_login.json()


@pytest.mark.parametrize(
    "login,password",
    [
        ("test_use", "password123"),
        ("test_user", "password1234"),
    ]
)
@pytest.mark.asyncio
async def test_login_fake_credentials(client, registered_user, login, password):
    response = await client.post(
        "/user/login",
        json={
            "login": login,
            "password": password,
        }
    )

    assert response.status_code == 401
    assert "token" not in response.cookies


@pytest.mark.asyncio
async def test_logout_and_me_without_cookie(client, logged_in_user):
    response_logout = await client.post(
        "/user/logout",
    )

    assert response_logout.status_code == 200
    assert "token" not in response_logout.cookies
    assert "token" not in client.cookies

    response_me = await client.get(
        "/user/me",
    )

    assert response_me.status_code == 401



@pytest.mark.parametrize(
    "case",
    [
        "expired", "missing_sub", "invalid_uuid", "null_sub", "numeric_sub",
        "unknown_user", "wrong_signature", "malformed", "invalid_exp",
    ],
)
@pytest.mark.asyncio
async def test_me_with_invalid_jwt(client, registered_user, case):
    payload = {
        "sub": registered_user["id"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    if case == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=5)
    elif case == "missing_sub":
        del payload["sub"]
    elif case == "invalid_uuid":
        payload["sub"] = "not-a-uuid"
    elif case == "null_sub":
        payload["sub"] = None
    elif case == "numeric_sub":
        payload["sub"] = 123
    elif case == "unknown_user":
        payload["sub"] = str(uuid4())
    elif case == "invalid_exp":
        payload["exp"] = "not-a-timestamp"

    token = jwt.encode(
        payload, auth_settings.secret_key, algorithm=auth_settings.algorithm
    )
    if case == "wrong_signature":
        header, body, signature = token.split(".")
        decoded = bytearray(urlsafe_b64decode(signature + "=" * (-len(signature) % 4)))
        decoded[0] ^= 1
        signature = urlsafe_b64encode(decoded).rstrip(b"=").decode()
        token = f"{header}.{body}.{signature}"
    elif case == "malformed":
        token = "invalid-token"

    client.cookies.set("token", token)
    response = await client.get("/user/me")

    assert response.status_code == 401
    assert "id" not in response.json()
    assert "hashed_password" not in response.json()


@pytest.mark.asyncio
async def test_me_without_cookie(client):
    response = await client.get("/user/me")

    assert response.status_code == 401


@pytest.mark.parametrize("duplicate_field", ["login", "email"])
@pytest.mark.asyncio
async def test_register_duplicate_field(
    client, registered_user, session_factory, duplicate_field
):
    payload = {
        "login": "different_user",
        "email": "different@example.com",
        "password": "another_password123",
    }
    payload[duplicate_field] = registered_user[duplicate_field]

    response = await client.post("/user/register", json=payload)

    assert response.status_code == 409
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Users)) == 1
        user = await session.get(Users, UUID(registered_user["id"]))
        assert user.login == registered_user["login"]
        assert user.email == registered_user["email"]
        assert verify_password("password123", user.hashed_password)


@pytest.mark.parametrize(
    "field,value",
    [
        ("login", ""), ("login", "ab"), ("login", "a" * 51), ("login", None),
        ("email", "invalid-email"), ("email", None),
        ("password", ""), ("password", "a" * 7),
        ("password", "a" * 129), ("password", None),
    ],
)
@pytest.mark.asyncio
async def test_register_invalid_data(client, session_factory, field, value):
    payload = {
        "login": "test_user", "email": "test@example.com", "password": "password123",
    }
    payload[field] = value

    response = await client.post("/user/register", json=payload)

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Users)) == 0


@pytest.mark.parametrize("field", ["login", "email", "password"])
@pytest.mark.asyncio
async def test_register_missing_field(client, session_factory, field):
    payload = {
        "login": "test_user", "email": "test@example.com", "password": "password123",
    }
    del payload[field]

    response = await client.post("/user/register", json=payload)

    assert response.status_code == 422
    assert any(error["loc"] == ["body", field] for error in response.json()["detail"])
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Users)) == 0


@pytest.mark.parametrize("login,password", [
    ("abc", "a" * 8),
    ("a" * 50, "a" * 128),
], ids=["minimum-lengths", "maximum-lengths"])
@pytest.mark.asyncio
async def test_register_valid_boundaries(client, login, password):
    response = await client.post(
        "/user/register",
        json={"login": login, "email": "test@example.com", "password": password},
    )
    assert response.status_code == 201
    user_id = response.json()["id"]

    response = await client.post("/user/login", json={"login": login, "password": password})
    assert response.status_code == 200
    assert response.json()["id"] == user_id


@pytest.mark.asyncio
async def test_register_cannot_set_admin(client, session_factory):
    response = await client.post(
        "/user/register",
        json={
            "login": "test_user", "email": "test@example.com",
            "password": "password123", "is_admin": True,
        },
    )

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "is_admin"] and error["type"] == "extra_forbidden"
        for error in response.json()["detail"]
    )
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Users)) == 0


@pytest.mark.parametrize("payload", [
    {},
    {"login": "test_user"},
    {"password": "password123"},
    {"login": None, "password": "password123"},
    {"login": "test_user", "password": None},
    {"login": "test_user", "password": "password123", "is_admin": True},
])
@pytest.mark.asyncio
async def test_login_invalid_data(client, registered_user, payload):
    response = await client.post("/user/login", json=payload)

    assert response.status_code == 422
    assert "token" not in client.cookies
    response = await client.get("/user/me")
    assert response.status_code == 401


@pytest.mark.parametrize("with_invalid_cookie", [False, True], ids=["no-cookie", "bad-cookie"])
@pytest.mark.asyncio
async def test_logout_without_valid_token(client, with_invalid_cookie):
    if with_invalid_cookie:
        client.cookies.set("token", "invalid-token", domain="test.local", path="/")

    response = await client.post("/user/logout")

    assert response.status_code == 200
    assert "token" not in client.cookies
    response = await client.get("/user/me")
    assert response.status_code == 401
