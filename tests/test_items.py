from decimal import Decimal
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_create_item(client, logged_in_admin):
    response = await client.post("/item/create", json={
        "name": "test",
        "description": "test",
        "price": str(Decimal(100)),
        "stock": 1,
    })

    assert response.status_code == 201

    data = response.json()

    assert set(data) == {
        "id", "name", "description", "price", "stock", "category_id",
    }
    assert data["name"] == "test"
    assert data["description"] == "test"
    assert Decimal(data["price"]) == Decimal("100.00")
    assert data["stock"] == 1
    assert data["category_id"] is None


@pytest.mark.asyncio
async def test_create_item_no_admin(client, logged_in_user):
    response = await client.post("/item/create", json={
        "name": "test",
        "description": "test",
        "price": str(Decimal(100)),
        "stock": 1,
    })

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_item_unlogged_user(client):
    response = await client.post("/item/create", json={
        "name": "test",
        "description": "test",
        "price": str(Decimal(100)),
        "stock": 1,
    })

    assert response.status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", ""),
        ("name", "a" * 257),
        ("price", "-123"),
        ("price", "1.001"),
        ("price", "100000000.00"),
        ("stock", "-1"),
        ("stock", "1.4"),
        ("category_id", "invalid"),
    ]
)
@pytest.mark.asyncio
async def test_create_item_invalid_field(client, logged_in_admin, field, value):
    item = {
        "name": "test",
        "description": "test",
        "price": str(Decimal(100)),
        "stock": 1,
    }
    item[field] = value

    response = await client.post("/item/create", json=item)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_category(client, logged_in_admin):
    response = await client.post("/item/category/create", json={"name": "test"})

    assert response.status_code == 201

    data = response.json()
    assert set(data) == {"id", "name"}
    assert data["name"] == "test"


@pytest.mark.asyncio
async def test_create_category_no_admin(client, logged_in_user):
    response = await client.post("/item/category/create", json={"name": "test"})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_category_unlogged_user(client):
    response = await client.post("/item/category/create", json={"name": "test"})

    assert response.status_code == 401


@pytest.mark.parametrize(
    "name",
    ["", "a" * 257, None],
)
@pytest.mark.asyncio
async def test_create_category_invalid_field(client, logged_in_admin, name):
    response = await client.post("/item/category/create", json={"name": name})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_item_by_id(client, created_item):
    client.cookies.clear()
    response = await client.get(f"/item/{created_item['id']}")

    assert response.status_code == 200

    data = response.json()
    assert set(data) == {"id", "name", "description", "price", "stock", "category_id"}
    assert data["id"] == created_item["id"]
    assert {**data, "price": Decimal(data["price"])} == {
        **created_item, "price": Decimal(created_item["price"]),
    }


@pytest.mark.asyncio
async def test_get_item_by_invalid_id(client):
    response = await client.get(f"/item/{uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_item_by_malformed_id(client):
    response = await client.get("/item/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.parametrize("price,stock", [("0.00", 1), ("10.00", 0), ("0.00", 0)])
@pytest.mark.asyncio
async def test_create_item_with_zero_price_or_stock(client, logged_in_admin, price, stock):
    response = await client.post(
        "/item/create", json={"name": "test", "price": price, "stock": stock}
    )

    assert response.status_code == 201
    item = response.json()
    assert Decimal(item["price"]) == Decimal(price)
    assert item["stock"] == stock

    response = await client.get(f"/item/{item['id']}")
    assert response.status_code == 200
    assert response.json() == item


@pytest.mark.parametrize("path", ["/item/items", "/item/categories"])
@pytest.mark.asyncio
async def test_get_empty_catalog_list(client, path):
    response = await client.get(path)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("path", ["/item/items", "/item/categories"])
@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page": "invalid"},
        {"limit": 0},
        {"limit": -1},
        {"limit": 21},
        {"limit": "invalid"},
    ],
)
@pytest.mark.asyncio
async def test_get_catalog_list_invalid_pagination(client, path, params):
    response = await client.get(path, params=params)

    assert response.status_code == 422


@pytest.mark.parametrize("resource", ["items", "categories"])
@pytest.mark.asyncio
async def test_get_catalog_list_pagination(client, logged_in_admin, resource):
    created = []
    for index in range(5):
        if resource == "items":
            path = "/item/create"
            payload = {"name": f"item_{index}", "price": "10.00", "stock": 1}
        else:
            path = "/item/category/create"
            payload = {"name": f"category_{index}"}

        response = await client.post(path, json=payload)
        assert response.status_code == 201
        created.append(response.json())

    client.cookies.clear()
    expected = sorted(created, key=lambda record: record["id"])
    received = []
    for page, size in [(1, 2), (2, 2), (3, 1), (4, 0)]:
        response = await client.get(
            f"/item/{resource}", params={"page": page, "limit": 2}
        )
        assert response.status_code == 200
        assert len(response.json()) == size
        received.extend(response.json())

    assert received == expected
    assert len({record["id"] for record in received}) == 5

    response = await client.get(f"/item/{resource}", params={"limit": 3})
    assert response.status_code == 200
    assert response.json() == expected[:3]


@pytest.mark.asyncio
async def test_create_item_with_category(client, created_category):
    response = await client.post(
        "/item/create",
        json={
            "name": "categorized_item",
            "price": "100.00",
            "stock": 1,
            "category_id": created_category["id"],
        },
    )

    assert response.status_code == 201
    item = response.json()
    assert item["category_id"] == created_category["id"]

    client.cookies.clear()
    response = await client.get(f"/item/{item['id']}")
    assert response.status_code == 200
    data = response.json()
    assert {**data, "price": Decimal(data["price"])} == {
        **item, "price": Decimal(item["price"]),
    }


@pytest.mark.asyncio
async def test_create_item_with_nonexistent_category(client, logged_in_admin):
    response = await client.post(
        "/item/create",
        json={
            "name": "test",
            "price": "100.00",
            "stock": 1,
            "category_id": str(uuid4()),
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Category not found"

    response = await client.get("/item/items")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_create_category_duplicate_name(client, created_category):
    response = await client.post(
        "/item/category/create", json={"name": created_category["name"]}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Category already exists"

    response = await client.get("/item/categories")
    assert response.status_code == 200
    assert response.json() == [created_category]

