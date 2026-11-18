from decimal import Decimal

import pytest_asyncio
from app.core.security import get_password_hash
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.session import get_session
from app.main import app

from app.core.config import db_settings
from app.models.models import Users

TEST_DB_URL = db_settings.async_db_url.set(database="test")


@pytest_asyncio.fixture
async def session_factory():
    async_engine = create_async_engine(TEST_DB_URL)

    if async_engine.url.database != "test":
        raise RuntimeError("Refusing to clean a non-test database")

    async with async_engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE orders, items, users, items_orders, categories"
        ))

    async_session_factory = async_sessionmaker(async_engine, expire_on_commit=False)
    try:
        yield async_session_factory
    finally:
        await async_engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)


@pytest_asyncio.fixture
async def registered_user(client):
    response = await client.post(
        "/user/register",
        json={
            "login": "test_user",
            "email": "test@example.com",
            "password": "password123",
        }
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def another_registered_user(client):
    response = await client.post(
        "/user/register",
        json={
            "login": "test_user1",
            "email": "test1@example.com",
            "password": "password123",
        }
    )
    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def logged_in_user(client, registered_user):
    response = await client.post(
        "/user/login",
        json={
            "login": registered_user["login"],
            "password": "password123",
        }
    )

    assert response.status_code == 200
    return response.json()


@pytest_asyncio.fixture
async def another_logged_in_user(client, another_registered_user):
    response = await client.post(
        "/user/login",
        json={
            "login": another_registered_user["login"],
            "password": "password123",
        }
    )

    assert response.status_code == 200
    return response.json()


@pytest_asyncio.fixture
async def logged_in_admin(client, session_factory):
    admin = Users(
        login="admin",
        email="admin@example.com",
        hashed_password=get_password_hash("admin123"),
        is_admin=True,
    )
    async with session_factory.begin() as session:
        session.add(admin)

    response = await client.post(
        "/user/login",
        json={
            "login": admin.login,
            "password": "admin123",
        }
    )

    assert response.status_code == 200
    return response.json()


@pytest_asyncio.fixture
async def created_item(client, logged_in_admin):
    response = await client.post(
        "/user/login",
        json={
            "login": logged_in_admin["login"],
            "password": "admin123",
        },
    )
    assert response.status_code == 200

    response = await client.post("/item/create", json={
        "name": "test",
        "description": "test",
        "price": str(Decimal(100)),
        "stock": 1,
    })

    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_another_item(client, logged_in_admin):
    response = await client.post(
        "/user/login",
        json={
            "login": logged_in_admin["login"],
            "password": "admin123",
        },
    )
    assert response.status_code == 200

    response = await client.post("/item/create", json={
        "name": "test1",
        "description": "test1",
        "price": str(Decimal(100)),
        "stock": 2,
    })

    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_multiple_items(client, logged_in_admin):
    response = await client.post(
        "/user/login",
        json={
            "login": logged_in_admin["login"],
            "password": "admin123",
        },
    )
    assert response.status_code == 200

    data = []

    for i in range(3):
        response = await client.post("/item/create", json={
            "name": f"test{i}",
            "description": f"test{1}",
            "price": str(Decimal(100)),
            "stock": 5,
        })
        data.append(response.json())

        assert response.status_code == 201
    return data


@pytest_asyncio.fixture
async def created_category(client, logged_in_admin):
    response = await client.post(
        "/user/login",
        json={
            "login": logged_in_admin["login"],
            "password": "admin123",
        },
    )
    assert response.status_code == 200

    response = await client.post("/item/category/create", json={"name": "test"})

    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_order(client, logged_in_user, created_item):
    response = await client.post(
        "/user/login",
        json={
            "login": logged_in_user["login"],
            "password": "password123",
        },
    )
    assert response.status_code == 200

    response = await client.post(
        "/order/create",
        json={
            "items": [
                {
                    "item_id": created_item["id"],
                    "quantity": 1
                }
            ]
        }
    )

    assert response.status_code == 201
    return response.json()


@pytest_asyncio.fixture
async def created_another_order(client, another_logged_in_user, created_another_item):
    response = await client.post(
        "/user/login",
        json={
            "login": another_logged_in_user["login"],
            "password": "password123",
        },
    )
    assert response.status_code == 200

    response = await client.post(
        "/order/create",
        json={
            "items": [
                {
                    "item_id": created_another_item["id"],
                    "quantity": 1
                }
            ]
        }
    )

    assert response.status_code == 201
    return response.json()
