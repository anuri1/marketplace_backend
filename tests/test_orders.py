import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from urllib import response

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import selectinload

from app.models.enums import OrderStatuses
from app.models.models import Items, ItemsOrders, Orders

from tests.conftest import created_multiple_items, logged_in_user


@pytest.mark.asyncio
async def test_create_order_single_item(client, logged_in_user, created_item):
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

    data = response.json()
    assert set(data.keys()) == {"id", "amount", "status", "created_at", "items"}
    assert data["items"][0]["item_id"] == created_item["id"]
    assert Decimal(data["amount"]) == Decimal(created_item["price"])
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_create_order_multiple_items(client, logged_in_user, created_multiple_items):
    response = await client.post(
        "/order/create",
        json={
            "items": [
                {
                    "item_id": created_multiple_items[0]["id"],
                    "quantity": 3
                },
                {
                    "item_id": created_multiple_items[1]["id"],
                    "quantity": 2
                },
                {
                    "item_id": created_multiple_items[2]["id"],
                    "quantity": 1
                }
            ]
        }
    )

    assert response.status_code == 201

    data = response.json()
    assert set(data.keys()) == {"id", "amount", "status", "created_at", "items"}
    positions = {item["item_id"]: item for item in data["items"]}
    assert len(data["items"]) == 3
    assert set(positions) == {item["id"] for item in created_multiple_items}

    quantities = [3, 2, 1]
    for item, quantity in zip(created_multiple_items, quantities):
        assert positions[item["id"]]["quantity"] == quantity
        assert Decimal(positions[item["id"]]["price"]) == Decimal(item["price"])
        item_response = await client.get(f"/item/{item['id']}")
        assert item_response.status_code == 200
        assert item_response.json()["stock"] == item["stock"] - quantity

    price = sum(
        Decimal(item["price"]) * quantity
        for item, quantity in zip(created_multiple_items, quantities)
    )
    assert Decimal(data["amount"]) == price
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_create_empty_order(client, logged_in_user):
    response = await client.post(
        "/order/create",
        json={"items": []}
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_order_lack_of_items(client, logged_in_user, created_item):
    response = await client.post(
        "/order/create",
        json={
            "items": [
                {
                    "item_id": created_item["id"],
                    "quantity": 2
                }
            ]
        }
    )

    assert response.status_code == 400

    response = await client.get(
        f"/item/{created_item['id']}",
    )

    assert response.status_code == 200
    assert response.json()["stock"] == 1


@pytest.mark.asyncio
async def test_create_order_lack_of_items_multiple_items(
    client, logged_in_user, created_multiple_items, session_factory
):
    await _login_for_order_test(client, logged_in_user["login"], "password123")
    items = sorted(created_multiple_items, key=lambda item: UUID(item["id"]))
    response = await client.post(
        "/order/create",
        json={
            "items": [
                {
                    "item_id": items[0]["id"],
                    "quantity": 3
                },
                {
                    "item_id": items[1]["id"],
                    "quantity": 2
                },
                {
                    "item_id": items[2]["id"],
                    "quantity": items[2]["stock"] + 1
                }
            ]
        }
    )

    assert response.status_code == 400

    await _assert_no_orders_and_unchanged_stock(session_factory, items)


@pytest.mark.asyncio
async def test_get_order(client, logged_in_user, created_order):
    response = await client.get(
        f"order/{created_order['id']}"
    )

    assert response.status_code == 200
    assert created_order == response.json()


@pytest.mark.asyncio
async def test_get_order_by_admin(client, logged_in_admin, created_order):
    response = await client.post(
        "/user/login",
        json={
            "login": logged_in_admin["login"],
            "password": "admin123",
        },
    )
    assert response.status_code == 200

    response = await client.get(
        f"order/{created_order['id']}"
    )

    assert response.status_code == 200
    assert created_order == response.json()


@pytest.mark.asyncio
async def test_get_order_unauthorized(client, created_order):
    response = await client.post(
        "/user/logout",
    )
    assert response.status_code == 200

    response = await client.get(
        f"order/{created_order['id']}"
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_order_wrong_user(client, created_order, another_logged_in_user):
    response = await client.post(
        "/user/logout",
    )
    assert response.status_code == 200

    response = await client.post(
        "/user/login",
        json={
            "login": another_logged_in_user["login"],
            "password": "password123",
        },
    )
    assert response.status_code == 200

    response = await client.get(
        f"order/{created_order['id']}"
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "login,password,key_params",
    [
        ("test_user", "password123", ["first"]),
        ("test_user1", "password123", ["second"]),
        ("admin", "admin123", ["first", "second"]),
    ]
)
@pytest.mark.asyncio
async def test_get_orders(client, created_order, created_another_order, login, password, key_params):
    orders = {
        "first": created_order["id"],
        "second": created_another_order["id"],
    }

    response = await client.post(
        "/user/logout"
    )
    assert response.status_code == 200

    response = await client.post(
        "/user/login",
        json={
            "login": login,
            "password": password,
        }
    )
    assert response.status_code == 200

    response = await client.get(
        "/order/orders"
    )
    assert response.status_code == 200

    expected_ids = {orders[key] for key in key_params}
    actual_ids = {order["id"] for order in response.json()}

    assert actual_ids == expected_ids
    assert len(response.json()) == len(expected_ids)


@pytest.mark.parametrize("as_admin", [False, True], ids=["owner", "admin"])
@pytest.mark.asyncio
async def test_get_orders_pagination(
    client, session_factory, logged_in_user, logged_in_admin, created_item, as_admin
):
    created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    orders = [
        Orders(
            user_id=UUID(logged_in_user["id"]),
            amount=Decimal("100.00"),
            created_at=created_at + timedelta(minutes=index // 2),
            items=[ItemsOrders(
                item_id=UUID(created_item["id"]),
                quantity=1,
                price=Decimal("100.00"),
            )],
        )
        for index in range(5)
    ]
    admin_order = Orders(
        user_id=UUID(logged_in_admin["id"]),
        amount=Decimal("100.00"),
        created_at=created_at + timedelta(minutes=3),
        items=[ItemsOrders(
            item_id=UUID(created_item["id"]),
            quantity=1,
            price=Decimal("100.00"),
        )],
    )
    async with session_factory.begin() as session:
        session.add_all([*orders, admin_order])

    user = logged_in_admin if as_admin else logged_in_user
    response = await client.post(
        "/user/login",
        json={
            "login": user["login"],
            "password": "admin123" if as_admin else "password123",
        },
    )
    assert response.status_code == 200

    visible_orders = [*orders, admin_order] if as_admin else orders
    expected_ids = [
        str(order.id)
        for order in sorted(
            visible_orders,
            key=lambda order: (-order.created_at.timestamp(), order.id),
        )
    ]
    received_ids = []
    for page in range(1, 5):
        response = await client.get(
            "/order/orders", params={"page": page, "limit": 2}
        )
        assert response.status_code == 200
        page_ids = [order["id"] for order in response.json()]
        assert page_ids == expected_ids[(page - 1) * 2:page * 2]
        received_ids.extend(page_ids)

    assert received_ids == expected_ids

    response = await client.get("/order/orders", params={"limit": 3})
    assert response.status_code == 200
    assert [order["id"] for order in response.json()] == expected_ids[:3]

    response = await client.get("/order/orders")
    assert response.status_code == 200
    assert [order["id"] for order in response.json()] == expected_ids[:5]


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page": "invalid"},
        {"page": 1.5},
        {"limit": 0},
        {"limit": -1},
        {"limit": 21},
        {"limit": "invalid"},
        {"limit": 1.5},
    ],
)
@pytest.mark.asyncio
async def test_get_orders_invalid_pagination(client, logged_in_user, params):
    response = await client.get("/order/orders", params=params)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_orders_unauthorized(client):
    response = await client.get("/order/orders")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_order_unauthorized(client, created_item, session_factory):
    client.cookies.clear()
    response = await client.post(
        "/order/create",
        json={"items": [{"item_id": created_item["id"], "quantity": 1}]},
    )

    assert response.status_code == 401
    await _assert_no_orders_and_unchanged_stock(session_factory, [created_item])


@pytest.mark.asyncio
async def test_create_order_with_missing_item(
    client, registered_user, created_item, session_factory
):
    await _login_for_order_test(client, registered_user["login"], "password123")
    missing_id = UUID(int=(1 << 128) - 1)
    assert UUID(created_item["id"]) < missing_id
    response = await client.post(
        "/order/create",
        json={"items": [
            {"item_id": created_item["id"], "quantity": 1},
            {"item_id": str(missing_id), "quantity": 1},
        ]},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"
    await _assert_no_orders_and_unchanged_stock(session_factory, [created_item])


@pytest.mark.parametrize(
    "field,value",
    [("quantity", 0), ("quantity", -1), ("quantity", 1.5), ("item_id", "not-a-uuid")],
    ids=["zero-quantity", "negative-quantity", "fractional-quantity", "invalid-item-id"],
)
@pytest.mark.asyncio
async def test_create_order_invalid_position(
    client, registered_user, created_item, session_factory, field, value
):
    await _login_for_order_test(client, registered_user["login"], "password123")
    position = {"item_id": created_item["id"], "quantity": 1}
    position[field] = value

    response = await client.post("/order/create", json={"items": [position]})

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "items", 0, field]
        for error in response.json()["detail"]
    )
    await _assert_no_orders_and_unchanged_stock(session_factory, [created_item])


@pytest.mark.asyncio
async def test_create_order_with_duplicate_item(
    client, registered_user, created_item, session_factory
):
    await _login_for_order_test(client, registered_user["login"], "password123")
    position = {"item_id": created_item["id"], "quantity": 1}

    response = await client.post("/order/create", json={"items": [position, position]})

    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "items"]
        for error in response.json()["detail"]
    )
    await _assert_no_orders_and_unchanged_stock(session_factory, [created_item])


@pytest.mark.asyncio
async def test_order_preserves_historical_price(client, created_order, session_factory):
    before = await _get_order_snapshot(session_factory, created_order["id"])
    item_id = created_order["items"][0]["item_id"]
    new_price = Decimal(created_order["items"][0]["price"]) + Decimal("12.34")
    async with session_factory.begin() as session:
        await session.execute(
            update(Items).where(Items.id == UUID(item_id)).values(price=new_price)
        )

    response = await client.get(f"/item/{item_id}")
    assert response.status_code == 200
    assert Decimal(response.json()["price"]) == new_price

    response = await client.get(f"/order/{created_order['id']}")
    assert response.status_code == 200
    assert response.json() == created_order
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.asyncio
async def test_create_order_with_different_decimal_prices(
    client, registered_user, created_multiple_items, session_factory
):
    prices = [Decimal("0.10"), Decimal("0.20"), Decimal("1.99")]
    quantities = [3, 2, 1]
    async with session_factory.begin() as session:
        for item, price in zip(created_multiple_items, prices):
            await session.execute(
                update(Items).where(Items.id == UUID(item["id"])).values(price=price)
            )
    await _login_for_order_test(client, registered_user["login"], "password123")

    response = await client.post(
        "/order/create",
        json={"items": [
            {"item_id": item["id"], "quantity": quantity}
            for item, quantity in zip(created_multiple_items, quantities)
        ]},
    )

    assert response.status_code == 201
    order = response.json()
    assert Decimal(order["amount"]) == Decimal("2.69")
    positions = {position["item_id"]: position for position in order["items"]}
    assert len(order["items"]) == len(positions) == 3
    for item, price, quantity in zip(created_multiple_items, prices, quantities):
        assert Decimal(positions[item["id"]]["price"]) == price
        assert positions[item["id"]]["quantity"] == quantity

    response = await client.get(f"/order/{order['id']}")
    assert response.status_code == 200
    assert response.json() == order
    snapshot = await _get_order_snapshot(session_factory, order["id"])
    assert snapshot["stocks"] == {
        item["id"]: item["stock"] - quantity
        for item, quantity in zip(created_multiple_items, quantities)
    }


@pytest.mark.parametrize("invalid_format", [False, True], ids=["missing", "invalid-uuid"])
@pytest.mark.asyncio
async def test_get_order_missing_or_invalid_id(client, logged_in_user, invalid_format):
    order_id = "not-a-uuid" if invalid_format else str(uuid4())

    response = await client.get(f"/order/{order_id}")

    assert response.status_code == (422 if invalid_format else 404)


async def _assert_no_orders_and_unchanged_stock(session_factory, items):
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Orders)) == 0
        assert await session.scalar(select(func.count()).select_from(ItemsOrders)) == 0
        for original in items:
            item = await session.get(Items, UUID(original["id"]))
            assert item is not None
            assert item.stock == original["stock"]


async def _login_for_order_test(client, login, password):
    response = await client.post(
        "/user/login", json={"login": login, "password": password}
    )
    assert response.status_code == 200


async def _set_order_status(session_factory, order_id, status):
    async with session_factory.begin() as session:
        await session.execute(
            update(Orders)
            .where(Orders.id == UUID(order_id))
            .values(status=status)
        )


async def _get_order_snapshot(session_factory, order_id):
    async with session_factory() as session:
        result = await session.execute(
            select(Orders)
            .where(Orders.id == UUID(order_id))
            .options(selectinload(Orders.items))
        )
        order = result.scalar_one()
        stocks = {}
        for position in order.items:
            item = await session.get(Items, position.item_id)
            stocks[str(item.id)] = item.stock
        return {
            "status": order.status,
            "user_id": order.user_id,
            "amount": order.amount,
            "created_at": order.created_at,
            "positions": sorted(
                (line.id, line.item_id, line.quantity, line.price)
                for line in order.items
            ),
            "stocks": stocks,
        }


@pytest.mark.parametrize("as_admin", [False, True], ids=["owner", "admin"])
@pytest.mark.asyncio
async def test_pay_own_order(client, created_order, session_factory, as_admin):
    if as_admin:
        await _login_for_order_test(client, "admin", "admin123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/pay")

    assert response.status_code == 200
    assert response.json() == {**created_order, "status": "paid"}
    after = await _get_order_snapshot(session_factory, created_order["id"])
    assert after == {**before, "status": OrderStatuses.paid}


@pytest.mark.asyncio
async def test_double_pay_order(client, created_order, session_factory):
    first = await client.patch(f"/order/{created_order['id']}/pay")
    assert first.status_code == 200
    before = await _get_order_snapshot(session_factory, created_order["id"])
    assert before["status"] == OrderStatuses.paid

    second = await client.patch(f"/order/{created_order['id']}/pay")

    assert second.status_code == 200
    assert second.json() == first.json()
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("status", [OrderStatuses.cancelled, OrderStatuses.completed])
@pytest.mark.parametrize("as_admin", [False, True], ids=["owner", "admin"])
@pytest.mark.asyncio
async def test_pay_wrong_status_order(
    session_factory, client, created_order, status, as_admin
):
    await _set_order_status(session_factory, created_order["id"], status)
    if as_admin:
        await _login_for_order_test(client, "admin", "admin123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/pay")

    assert response.status_code == 409
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("status", list(OrderStatuses))
@pytest.mark.asyncio
async def test_pay_order_wrong_user(
    client, created_order, another_registered_user, session_factory, status
):
    await _set_order_status(session_factory, created_order["id"], status)
    await _login_for_order_test(client, another_registered_user["login"], "password123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/pay")

    assert response.status_code == 404
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("action,status", [
    ("pay", OrderStatuses.created),
    ("complete", OrderStatuses.paid),
])
@pytest.mark.asyncio
async def test_pay_or_complete_unauthorized(
    client, created_order, session_factory, action, status
):
    await _set_order_status(session_factory, created_order["id"], status)
    before = await _get_order_snapshot(session_factory, created_order["id"])
    client.cookies.clear()

    response = await client.patch(f"/order/{created_order['id']}/{action}")

    assert response.status_code == 401
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("action,as_admin", [
    ("pay", False), ("pay", True), ("complete", True),
])
@pytest.mark.asyncio
async def test_pay_or_complete_missing_order(
    client, logged_in_user, logged_in_admin, action, as_admin
):
    await _login_for_order_test(
        client,
        logged_in_admin["login"] if as_admin else logged_in_user["login"],
        "admin123" if as_admin else "password123",
    )

    response = await client.patch(f"/order/{uuid4()}/{action}")

    assert response.status_code == 404


@pytest.mark.parametrize("action", ["pay", "complete"])
@pytest.mark.asyncio
async def test_pay_or_complete_invalid_id(client, logged_in_admin, action):
    response = await client.patch(f"/order/not-a-uuid/{action}")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_complete_paid_order(client, created_order, session_factory):
    payment = await client.patch(f"/order/{created_order['id']}/pay")
    assert payment.status_code == 200
    await _login_for_order_test(client, "admin", "admin123")
    before = await _get_order_snapshot(session_factory, created_order["id"])
    assert before["status"] == OrderStatuses.paid

    response = await client.patch(f"/order/{created_order['id']}/complete")

    assert response.status_code == 200
    assert response.json() == {**payment.json(), "status": "completed"}
    after = await _get_order_snapshot(session_factory, created_order["id"])
    assert after == {**before, "status": OrderStatuses.completed}


@pytest.mark.asyncio
async def test_double_complete_order(client, created_order, session_factory):
    payment = await client.patch(f"/order/{created_order['id']}/pay")
    assert payment.status_code == 200
    await _login_for_order_test(client, "admin", "admin123")
    first = await client.patch(f"/order/{created_order['id']}/complete")
    assert first.status_code == 200
    before = await _get_order_snapshot(session_factory, created_order["id"])
    assert before["status"] == OrderStatuses.completed

    second = await client.patch(f"/order/{created_order['id']}/complete")

    assert second.status_code == 200
    assert second.json() == first.json()
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("status", [OrderStatuses.created, OrderStatuses.cancelled])
@pytest.mark.asyncio
async def test_complete_wrong_status_order(
    client, created_order, session_factory, status
):
    await _set_order_status(session_factory, created_order["id"], status)
    await _login_for_order_test(client, "admin", "admin123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/complete")

    assert response.status_code == 409
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("status", list(OrderStatuses))
@pytest.mark.parametrize("is_owner", [True, False], ids=["owner", "other-user"])
@pytest.mark.asyncio
async def test_complete_order_no_admin(
    client, created_order, registered_user, another_registered_user,
    session_factory, status, is_owner,
):
    await _set_order_status(session_factory, created_order["id"], status)
    user = registered_user if is_owner else another_registered_user
    await _login_for_order_test(client, user["login"], "password123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/complete")

    assert response.status_code == 403
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("as_admin", [False, True], ids=["owner", "admin"])
@pytest.mark.asyncio
async def test_cancel_order(client, created_order, session_factory, as_admin):
    if as_admin:
        await _login_for_order_test(client, "admin", "admin123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/cancel")

    assert response.status_code == 200
    assert response.json() == {**created_order, "status": "cancelled"}
    expected_stocks = before["stocks"].copy()
    for position in created_order["items"]:
        expected_stocks[position["item_id"]] += position["quantity"]
    after = await _get_order_snapshot(session_factory, created_order["id"])
    assert after == {
        **before, "status": OrderStatuses.cancelled, "stocks": expected_stocks,
    }


@pytest.mark.asyncio
async def test_double_cancel_order(client, created_order, session_factory):
    first = await client.patch(f"/order/{created_order['id']}/cancel")
    assert first.status_code == 200
    before = await _get_order_snapshot(session_factory, created_order["id"])
    assert before["status"] == OrderStatuses.cancelled

    second = await client.patch(f"/order/{created_order['id']}/cancel")

    assert second.status_code == 409
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("status", [OrderStatuses.paid, OrderStatuses.completed])
@pytest.mark.parametrize("as_admin", [False, True], ids=["owner", "admin"])
@pytest.mark.asyncio
async def test_cancel_wrong_status_order(
    client, created_order, session_factory, status, as_admin
):
    await _set_order_status(session_factory, created_order["id"], status)
    if as_admin:
        await _login_for_order_test(client, "admin", "admin123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/cancel")

    assert response.status_code == 409
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("status", list(OrderStatuses))
@pytest.mark.asyncio
async def test_cancel_order_wrong_user(
    client, created_order, another_registered_user, session_factory, status
):
    await _set_order_status(session_factory, created_order["id"], status)
    await _login_for_order_test(client, another_registered_user["login"], "password123")
    before = await _get_order_snapshot(session_factory, created_order["id"])

    response = await client.patch(f"/order/{created_order['id']}/cancel")

    assert response.status_code == 404
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.asyncio
async def test_cancel_order_unauthorized(client, created_order, session_factory):
    before = await _get_order_snapshot(session_factory, created_order["id"])
    client.cookies.clear()

    response = await client.patch(f"/order/{created_order['id']}/cancel")

    assert response.status_code == 401
    assert await _get_order_snapshot(session_factory, created_order["id"]) == before


@pytest.mark.parametrize("as_admin", [False, True], ids=["user", "admin"])
@pytest.mark.asyncio
async def test_cancel_missing_order(
    client, logged_in_user, logged_in_admin, as_admin
):
    await _login_for_order_test(
        client,
        logged_in_admin["login"] if as_admin else logged_in_user["login"],
        "admin123" if as_admin else "password123",
    )

    response = await client.patch(f"/order/{uuid4()}/cancel")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_order_invalid_id(client, logged_in_user):
    response = await client.patch("/order/not-a-uuid/cancel")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_cancel_order_restores_multiple_items(
    client, created_multiple_items, registered_user, session_factory
):
    await _login_for_order_test(client, registered_user["login"], "password123")
    response = await client.post(
        "/order/create",
        json={"items": [
            {"item_id": item["id"], "quantity": quantity}
            for item, quantity in zip(created_multiple_items, [3, 2, 1])
        ]},
    )
    assert response.status_code == 201
    order = response.json()
    before = await _get_order_snapshot(session_factory, order["id"])
    original_stocks = {item["id"]: item["stock"] for item in created_multiple_items}
    for position in order["items"]:
        item_id = position["item_id"]
        assert before["stocks"][item_id] == original_stocks[item_id] - position["quantity"]

    response = await client.patch(f"/order/{order['id']}/cancel")

    assert response.status_code == 200
    assert response.json() == {**order, "status": "cancelled"}
    after = await _get_order_snapshot(session_factory, order["id"])
    assert after == {
        **before, "status": OrderStatuses.cancelled, "stocks": original_stocks,
    }


async def _run_competing_requests(session_factory, model, row_id, requests):
    count_waiters = text("""
        WITH RECURSIVE blocked(pid) AS (
            SELECT CAST(:blocker_pid AS integer)
            UNION
            SELECT activity.pid
            FROM pg_stat_activity AS activity
            JOIN blocked ON blocked.pid = ANY(pg_blocking_pids(activity.pid))
            WHERE activity.datname = current_database()
        )
        SELECT count(*) - 1 FROM blocked
    """)
    tasks = []
    async with asyncio.timeout(15):
        async with asyncio.TaskGroup() as group:
            async with session_factory.begin() as blocker:
                locked_id = await blocker.scalar(
                    select(model.id).where(model.id == UUID(row_id)).with_for_update()
                )
                assert locked_id is not None
                blocker_pid = await blocker.scalar(text("SELECT pg_backend_pid()"))

                async with session_factory() as observer:
                    for request in requests:
                        tasks.append(group.create_task(request()))
                        while True:
                            waiting = await observer.scalar(
                                count_waiters, {"blocker_pid": blocker_pid}
                            )
                            await observer.rollback()
                            assert not any(task.done() for task in tasks), (
                                "Запрос завершился, не дождавшись снятия блокировки"
                            )
                            if waiting == len(tasks):
                                break
                            await asyncio.sleep(0.01)
        return [task.result() for task in tasks]


@pytest.mark.asyncio
async def test_concurrent_orders_for_last_item(
    client, logged_in_user, created_item, session_factory
):
    await _login_for_order_test(client, logged_in_user["login"], "password123")
    assert created_item["stock"] == 1
    payload = {"items": [{"item_id": created_item["id"], "quantity": 1}]}

    responses = await _run_competing_requests(
        session_factory, Items, created_item["id"],
        [
            lambda: client.post("/order/create", json=payload),
            lambda: client.post("/order/create", json=payload),
        ],
    )

    assert sorted(result.status_code for result in responses) == [201, 400]
    success = next(result.json() for result in responses if result.status_code == 201)
    failure = next(result.json() for result in responses if result.status_code == 400)
    assert failure["detail"] == "Not enough items"

    async with session_factory() as session:
        item = await session.get(Items, UUID(created_item["id"]))
        orders = list(await session.scalars(select(Orders)))
        lines = list(await session.scalars(select(ItemsOrders)))
        assert item.stock == 0
        assert len(orders) == len(lines) == 1
        assert str(orders[0].id) == success["id"]
        assert orders[0].user_id == UUID(logged_in_user["id"])
        assert orders[0].status == OrderStatuses.created
        assert orders[0].amount == Decimal(created_item["price"])
        assert lines[0].order_id == orders[0].id
        assert lines[0].item_id == item.id
        assert lines[0].quantity == 1
        assert lines[0].price == item.price


@pytest.mark.asyncio
async def test_concurrent_cancel_returns_stock_once(client, created_order, session_factory):
    before = await _get_order_snapshot(session_factory, created_order["id"])
    url = f"/order/{created_order['id']}/cancel"

    responses = await _run_competing_requests(
        session_factory, Orders, created_order["id"],
        [lambda: client.patch(url), lambda: client.patch(url)],
    )

    assert sorted(result.status_code for result in responses) == [200, 409]
    success = next(result.json() for result in responses if result.status_code == 200)
    assert success == {**created_order, "status": "cancelled"}
    expected_stocks = before["stocks"].copy()
    for position in created_order["items"]:
        expected_stocks[position["item_id"]] += position["quantity"]
    assert await _get_order_snapshot(session_factory, created_order["id"]) == {
        **before, "status": OrderStatuses.cancelled, "stocks": expected_stocks,
    }


@pytest.mark.parametrize("first_action", ["pay", "cancel"])
@pytest.mark.asyncio
async def test_concurrent_pay_and_cancel(
    client, created_order, session_factory, first_action
):
    before = await _get_order_snapshot(session_factory, created_order["id"])
    second_action = "cancel" if first_action == "pay" else "pay"
    url = f"/order/{created_order['id']}"

    first, second = await _run_competing_requests(
        session_factory, Orders, created_order["id"],
        [
            lambda: client.patch(f"{url}/{first_action}"),
            lambda: client.patch(f"{url}/{second_action}"),
        ],
    )

    assert first.status_code == 200
    assert second.status_code == 409
    expected_status = (
        OrderStatuses.paid if first_action == "pay" else OrderStatuses.cancelled
    )
    assert first.json() == {**created_order, "status": expected_status.value}
    expected_stocks = before["stocks"].copy()
    if first_action == "cancel":
        for position in created_order["items"]:
            expected_stocks[position["item_id"]] += position["quantity"]
    assert await _get_order_snapshot(session_factory, created_order["id"]) == {
        **before, "status": expected_status, "stocks": expected_stocks,
    }
