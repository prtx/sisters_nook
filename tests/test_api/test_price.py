from decimal import Decimal

from sisters_nook.schema import MenuItemPriceHistory, Order
from tests.test_api.conftest import admin_employee, api_headers


def test_PRICE_001_menu_prices_present(admin_employee, client):
    admin = admin_employee["admin"]
    resp = client.get("/api/menu", headers=api_headers(admin))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data
    assert all(Decimal(item["price"]) >= Decimal("0.00") for item in data)


def test_PRICE_002_history_recorded_when_price_changes(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    latte_id = admin_employee["latte"].id
    resp = client.put(
        f"/api/menu/{latte_id}",
        headers=api_headers(admin),
        json={"price": "4.75"},
    )
    assert resp.status_code == 200

    session.expire_all()
    history = (
        session.query(MenuItemPriceHistory)
        .filter_by(menu_item_id=latte_id)
        .order_by(MenuItemPriceHistory.changed_at.desc())
        .first()
    )
    assert history is not None
    assert history.new_price == Decimal("4.75")
    assert history.old_price == Decimal("4.50")


def test_PRICE_003_negative_price_rejected(admin_employee, client):
    admin = admin_employee["admin"]
    resp = client.post(
        "/api/menu",
        headers=api_headers(admin),
        json={"name": "Bad", "price": "-1.00"},
    )
    assert resp.status_code == 400


def test_PRICE_006_orders_keep_snapshot_after_price_change(admin_employee, client):
    admin = admin_employee["admin"]
    employee = admin_employee["employee"]
    session = admin_employee["session"]
    latte = admin_employee["latte"]
    order_resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = order_resp.get_json()["id"]

    client.put(
        f"/api/menu/{latte.id}",
        headers=api_headers(admin),
        json={"price": "5.00"},
    )

    session.expire_all()
    stored_order = session.get(Order, order_id)
    snapshot = stored_order.order_items[0]
    assert snapshot.unit_price_snapshot == Decimal("4.50")
